import os
import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from sudodev.server.models import AgentRunRequest, AgentRunResponse, AgentStatusResponse
from sudodev.core.unified_agent import UnifiedAgent
from sudodev.server.routes.ide import router as ide_router
from sudodev.db.database import create_all_tables, get_db
from sudodev.db import crud

swe_bench_dataset = None
cache_manager = None


def load_swebench():
    global swe_bench_dataset, cache_manager
    if swe_bench_dataset is not None:
        return True

    try:
        from datasets import load_dataset
        from sudodev.core.cache_manager import InstanceCacheManager

        print("Loading SWE-bench dataset...")
        swe_bench_dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        print(f"Loaded {len(swe_bench_dataset)} issues from SWE-bench")

        if os.path.exists("/app"):
            cache_dir = os.getenv("SWEBENCH_CACHE_DIR", "/app/cache/swebench")
        else:
            cache_dir = os.getenv("SWEBENCH_CACHE_DIR", "./cache/swebench")

        cache_manager = InstanceCacheManager(cache_dir)
        print(f"Cache manager initialized at {cache_dir}")
        return True

    except Exception as e:
        print(f"SWE-bench dataset not available: {e}")
        print("SWE-bench mode will be disabled. GitHub mode is still available.")
        return False


# --- In-memory fallback for agent runs (used alongside DB) ---
agent_runs = {}


def add_log(run_id: str, message: str, step: int = None):
    """Add a log message to the agent run (in-memory)."""
    if run_id in agent_runs:
        agent_runs[run_id]["logs"].append(message)
        if step is not None:
            agent_runs[run_id]["current_step"] = step


class LogCaptureHandler(logging.Handler):
    """Custom logging handler to capture agent logs."""
    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id
        self.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')
        self.setFormatter(formatter)

    def emit(self, record):
        try:
            msg = self.format(record)
            if msg.strip():
                add_log(self.run_id, msg)
        except Exception:
            pass


def run_agent(run_id: str, request: AgentRunRequest):
    """Execute the real SudoDev agent."""
    import time
    from sudodev.core.improved_agent import ImprovedAgent
    from sudodev.core.utils.logger import setup_logger

    agent_runs[run_id]["status"] = "running"
    agent_runs[run_id]["message"] = "Preparing instance..."

    log_handler = LogCaptureHandler(run_id)
    root_logger = logging.getLogger()
    root_logger.addHandler(log_handler)

    try:
        if request.mode == "swebench":
            if not load_swebench():
                raise RuntimeError("SWE-bench dataset is not available. Install 'datasets' package.")

            add_log(run_id, f"[INIT] Loading issue {request.instance_id}...", 0)
            issue = next(
                (item for item in swe_bench_dataset if item["instance_id"] == request.instance_id),
                None
            )

            if not issue:
                raise FileNotFoundError(f"Instance {request.instance_id} not found in SWE-bench dataset")

            add_log(run_id, f"[CACHE] Checking cache for {request.instance_id}...", 0)
            if not cache_manager.is_instance_cached(request.instance_id):
                add_log(run_id, f"[CACHE] Instance not cached, downloading from SWE-bench...", 0)
                agent_runs[run_id]["message"] = "Downloading instance environment..."

                if not cache_manager.download_instance(request.instance_id):
                    raise Exception(f"Failed to download instance {request.instance_id}")

                add_log(run_id, f"[CACHE] Instance cached successfully", 0)
            else:
                add_log(run_id, f"[CACHE] Using cached instance", 0)

            agent = UnifiedAgent(mode="swebench", issue_data=issue)

        elif request.mode == "github":
            add_log(run_id, f"[INIT] Processing GitHub repository...", 0)
            add_log(run_id, f"[REPO] URL: {request.github_url}", 0)
            add_log(run_id, f"[REPO] Branch: {request.branch}", 0)

            if request.issue_url:
                add_log(run_id, f"[ISSUE] Fetched from GitHub: {request.issue_url}", 0)
            elif request.issue_number:
                add_log(run_id, f"[ISSUE] Using GitHub issue #{request.issue_number}", 0)
            else:
                add_log(run_id, f"[ISSUE] Using manual description", 0)

            add_log(run_id, f"[BUILD] Setting up E2B sandbox environment...", 0)
            agent_runs[run_id]["message"] = "Cloning repository and setting up environment..."

            repo_name = request.github_url.split('/')[-1].replace('.git', '')

            agent = UnifiedAgent(
                mode="github",
                github_url=request.github_url,
                branch=request.branch,
                issue_description=request.issue_description,
                repo_name=repo_name
            )

            add_log(run_id, f"[BUILD] E2B sandbox ready", 0)

        else:
            raise ValueError(f"Unknown mode: {request.mode}")

        add_log(run_id, f"[AGENT] Starting analysis...", 1)
        agent_runs[run_id]["message"] = "Agent is analyzing the issue..."

        success = agent.run()

        patch = ""
        if success:
            patch = agent.get_patch()
        agent_runs[run_id]["patch"] = patch

        if success:
            add_log(run_id, "[COMPLETE] Fix generated successfully", 5)
            agent_runs[run_id]["status"] = "completed"
            agent_runs[run_id]["message"] = "Fix generated successfully"
        else:
            add_log(run_id, "[ERROR] Agent could not generate a fix")
            agent_runs[run_id]["status"] = "failed"
            agent_runs[run_id]["message"] = "Agent could not resolve the issue"

    except FileNotFoundError as e:
        error_msg = f"Instance not found: {str(e)}"
        add_log(run_id, f"[ERROR] {error_msg}")
        agent_runs[run_id]["status"] = "failed"
        agent_runs[run_id]["message"] = error_msg

    except ValueError as e:
        error_msg = str(e)
        add_log(run_id, f"[ERROR] {error_msg}")
        agent_runs[run_id]["status"] = "failed"
        agent_runs[run_id]["message"] = f"Validation error: {error_msg}"

    except Exception as e:
        error_msg = str(e)
        add_log(run_id, f"[ERROR] {error_msg}")
        agent_runs[run_id]["status"] = "failed"
        agent_runs[run_id]["message"] = f"Error: {error_msg}"

        import traceback
        traceback.print_exc()
    finally:
        root_logger.removeHandler(log_handler)


# --- API key verification for protected routes ---
API_SECRET_KEY = os.getenv("API_SECRET_KEY")


async def verify_api_key(request: Request):
    """Optional API key verification for production."""
    if not API_SECRET_KEY:
        return  # No key configured, skip verification
    auth_header = request.headers.get("X-API-Key")
    if auth_header != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# --- Application lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup."""
    await create_all_tables()
    yield


app = FastAPI(lifespan=lifespan)

# Phase 7: CORS hardening — configurable allowed origins
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:3001"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ide_router)


@app.get("/")
def root():
    swebench_available = swe_bench_dataset is not None
    modes = ["github"]
    if swebench_available:
        modes.insert(0, "swebench")

    return {
        "message": "SudoDev API",
        "version": "0.3.0",
        "modes": modes,
        "swebench_available": swebench_available
    }


@app.post("/api/run")
def start_run(request: AgentRunRequest, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())

    agent_runs[run_id] = {
        "status": "pending",
        "mode": request.mode,
        "instance_id": request.instance_id if request.mode == "swebench" else None,
        "github_url": request.github_url if request.mode == "github" else None,
        "problem_statement": request.problem_statement or request.issue_description,
        "created_at": datetime.now().isoformat(),
        "logs": [],
        "current_step": 0,
        "patch": "",
        "message": "Initializing..."
    }

    # Try Celery dispatch if Redis is configured, else fall back to BackgroundTasks
    redis_url = os.getenv("UPSTASH_REDIS_URL")
    if redis_url:
        try:
            from sudodev.worker.tasks import run_agent_task
            issue_data = {
                "instance_id": request.instance_id,
                "problem_statement": request.problem_statement or request.issue_description,
                "github_url": request.github_url,
                "branch": request.branch,
            }
            run_agent_task.delay(run_id, request.mode, issue_data)
        except Exception as e:
            logging.warning(f"Celery dispatch failed, falling back to BackgroundTasks: {e}")
            background_tasks.add_task(run_agent, run_id, request)
    else:
        background_tasks.add_task(run_agent, run_id, request)

    return AgentRunResponse(
        run_id=run_id,
        status="pending",
        message=f"Started {request.mode} mode agent run"
    )


@app.get("/api/status/{run_id}")
def get_status(run_id: str):
    if run_id not in agent_runs:
        return {"error": "Run not found"}

    run = agent_runs[run_id]
    return AgentStatusResponse(
        run_id=run_id,
        status=run["status"],
        message=run.get("message"),
        logs=run.get("logs", []),
        current_step=run.get("current_step", 0),
        patch=run.get("patch", "")
    )


@app.get("/api/runs")
def list_runs():
    return {
        "runs": [
            {
                "run_id": run_id,
                "mode": run["mode"],
                "status": run["status"],
                "created_at": run["created_at"]
            }
            for run_id, run in agent_runs.items()
        ]
    }


@app.get("/api/cache/status")
def cache_status():
    if not load_swebench():
        return {"error": "SWE-bench not available", "cached_instances": [], "total_cached": 0}
    return cache_manager.get_cache_info()


@app.delete("/api/cache/clear")
def clear_cache(instance_id: str = None):
    if not load_swebench():
        return {"error": "SWE-bench not available"}
    cache_manager.clear_cache(instance_id)
    return {"message": f"Cache cleared for {instance_id}" if instance_id else "All cache cleared"}


@app.get("/api/docker/status/{instance_id}")
def docker_image_status(instance_id: str):
    if not load_swebench():
        return {"instance_id": instance_id, "image_exists": False, "cached": False}
    return cache_manager.get_docker_image_status(instance_id)


@app.post("/api/docker/build/{instance_id}")
def build_docker_image(instance_id: str):
    if not load_swebench():
        return {"success": False, "instance_id": instance_id, "message": "SWE-bench not available"}

    status = cache_manager.get_docker_image_status(instance_id)

    if status["image_exists"]:
        print(f"Docker image already exists for {instance_id}")
        return {
            "success": True,
            "instance_id": instance_id,
            "message": "Docker image already exists",
            "already_exists": True
        }

    try:
        result = cache_manager.build_docker_image(instance_id)
        return result
    except Exception as e:
        logging.error(f"Build failed for {instance_id}: {e}")
        return {
            "success": False,
            "instance_id": instance_id,
            "message": str(e),
            "error": str(e)
        }


@app.get("/api/instances")
def list_swebench_instances():
    if not load_swebench():
        return {"instances": [], "total": 0, "message": "SWE-bench not available"}

    instances = []
    for item in swe_bench_dataset:
        instances.append({
            "instance_id": item["instance_id"],
            "repo": item.get("repo", ""),
            "has_docker": cache_manager._docker_image_exists(item["instance_id"])
        })
    return {"instances": instances, "total": len(instances)}

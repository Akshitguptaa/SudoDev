import asyncio
import logging
from sudodev.worker.celery_app import app
from sudodev.db.database import async_session
from sudodev.db import crud


class DBLogHandler(logging.Handler):
    """Logging handler that writes logs to the database for a specific run."""

    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id
        self.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        self.setFormatter(formatter)

    def emit(self, record):
        try:
            msg = self.format(record)
            if msg.strip():
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._append_log(msg))
                loop.close()
        except Exception:
            pass

    async def _append_log(self, message: str):
        async with async_session() as db:
            await crud.append_log(db, self.run_id, message)


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_agent_task(self, run_id: str, mode: str, issue_data: dict):
    """Celery task that runs the SudoDev agent."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_run_agent_async(run_id, mode, issue_data))
    except Exception as exc:
        loop.run_until_complete(_mark_failed(run_id, str(exc)))
        raise self.retry(exc=exc)
    finally:
        loop.close()


async def _run_agent_async(run_id: str, mode: str, issue_data: dict):
    """Async wrapper for the agent execution."""
    from sudodev.core.unified_agent import UnifiedAgent

    async with async_session() as db:
        await crud.update_run_status(db, run_id, "running", "Preparing instance...")

    log_handler = DBLogHandler(run_id)
    root_logger = logging.getLogger()
    root_logger.addHandler(log_handler)

    try:
        if mode == "swebench":
            agent = UnifiedAgent(mode="swebench", issue_data=issue_data)
        elif mode == "github":
            github_url = issue_data.get("repo", issue_data.get("github_url", ""))
            branch = issue_data.get("branch", "main")
            issue_description = issue_data.get("problem_statement", "")
            repo_name = github_url.split("/")[-1].replace(".git", "") if github_url else "custom"

            agent = UnifiedAgent(
                mode="github",
                github_url=github_url,
                branch=branch,
                issue_description=issue_description,
                repo_name=repo_name,
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")

        success = agent.run()
        patch = agent.get_patch() if success else ""

        async with async_session() as db:
            if success:
                await crud.update_run_status(
                    db, run_id, "completed", "Fix generated successfully", patch
                )
            else:
                await crud.update_run_status(
                    db, run_id, "failed", "Agent could not resolve the issue"
                )

    except Exception as e:
        async with async_session() as db:
            await crud.update_run_status(db, run_id, "failed", f"Error: {str(e)}")
        raise
    finally:
        root_logger.removeHandler(log_handler)


async def _mark_failed(run_id: str, error_msg: str):
    async with async_session() as db:
        await crud.update_run_status(db, run_id, "failed", f"Error: {error_msg}")

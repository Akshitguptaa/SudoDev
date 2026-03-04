import uuid
from datetime import datetime
from typing import Dict
from fastapi import APIRouter, BackgroundTasks, HTTPException
from sudodev.server.models import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStatusResponse,
)
from sudodev.core.improved_agent import ImprovedAgent

router = APIRouter()

# Simple in-memory storage
agent_runs: Dict[str, Dict] = {}


def run_agent_task(run_id: str, issue_data: Dict):
    """Background task to run the agent."""
    try:
        agent_runs[run_id]["status"] = "running"
        agent_runs[run_id]["started_at"] = datetime.now().isoformat()
        
        # Run the agent
        agent = ImprovedAgent(issue_data)
        success = agent.run()
        
        # Update status
        if success:
            agent_runs[run_id]["status"] = "completed"
            agent_runs[run_id]["output"] = {"success": True}
        else:
            agent_runs[run_id]["status"] = "failed"
            agent_runs[run_id]["error"] = "Agent failed to generate a fix"
        
        agent_runs[run_id]["completed_at"] = datetime.now().isoformat()
            
    except Exception as e:
        agent_runs[run_id]["status"] = "failed"
        agent_runs[run_id]["error"] = str(e)
        agent_runs[run_id]["completed_at"] = datetime.now().isoformat()


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(request: AgentRunRequest, background_tasks: BackgroundTasks):
    """Start an agent run."""
    run_id = str(uuid.uuid4())
    
    issue_data = {
        "instance_id": request.instance_id,
        "problem_statement": request.problem_statement or request.issue_description,
    }
    
    agent_runs[run_id] = {
        "run_id": run_id,
        "status": "pending",
        "issue_data": issue_data,
        "created_at": datetime.now().isoformat()
    }
    
    background_tasks.add_task(run_agent_task, run_id, issue_data)
    
    return AgentRunResponse(
        run_id=run_id,
        status="pending",
        message="Agent run started"
    )


@router.get("/status/{run_id}", response_model=AgentStatusResponse)
async def get_status(run_id: str):
    """Get agent run status."""
    if run_id not in agent_runs:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run = agent_runs[run_id]
    return AgentStatusResponse(
        run_id=run_id,
        status=run["status"],
        message=run.get("error"),
        logs=run.get("logs", []),
        current_step=run.get("current_step", 0),
        patch=run.get("patch", "")
    )


@router.get("/runs")
async def list_runs():
    """List all agent runs."""
    return {
        "runs": [
            {
                "run_id": run_id,
                "status": run["status"],
                "instance_id": run["issue_data"].get("instance_id"),
                "created_at": run["created_at"]
            }
            for run_id, run in agent_runs.items()
        ]
    }

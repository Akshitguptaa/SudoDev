import uuid
import asyncio
import threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from pydantic import BaseModel

from sudodev.runtime.ide_sandbox import IDESandbox
from sudodev.core.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/ide", tags=["IDE"])

ide_sessions: dict[str, dict] = {}

class IDESessionRequest(BaseModel):
    mode: str  # "swebench" or "github"
    instance_id: Optional[str] = None
    github_url: Optional[str] = None
    branch: Optional[str] = "main"


class IDESessionResponse(BaseModel):
    session_id: str
    status: str
    message: Optional[str] = None
    mode: Optional[str] = None
    instance_id: Optional[str] = None
    github_url: Optional[str] = None
    created_at: Optional[str] = None


class FileWriteRequest(BaseModel):
    path: str
    content: str


@router.post("/session", response_model=IDESessionResponse)
def create_session(request: IDESessionRequest):
    if request.mode == "swebench" and not request.instance_id:
        raise HTTPException(status_code=400, detail="instance_id required for swebench mode")
    if request.mode == "github" and not request.github_url:
        raise HTTPException(status_code=400, detail="github_url required for github mode")

    session_id = str(uuid.uuid4())

    try:
        sandbox = IDESandbox(
            mode=request.mode,
            instance_id=request.instance_id,
            github_url=request.github_url,
            branch=request.branch or "main",
        )
        sandbox.start()

        ide_sessions[session_id] = {
            "sandbox": sandbox,
            "status": "running",
            "mode": request.mode,
            "instance_id": request.instance_id,
            "github_url": request.github_url,
            "created_at": datetime.now().isoformat(),
        }

        return IDESessionResponse(
            session_id=session_id,
            status="running",
            message="IDE session started",
            mode=request.mode,
            instance_id=request.instance_id,
            github_url=request.github_url,
            created_at=ide_sessions[session_id]["created_at"],
        )

    except Exception as e:
        logger.error(f"Failed to create IDE session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}", response_model=IDESessionResponse)
def get_session(session_id: str):
    if session_id not in ide_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    sess = ide_sessions[session_id]
    return IDESessionResponse(
        session_id=session_id,
        status=sess["status"],
        mode=sess["mode"],
        instance_id=sess.get("instance_id"),
        github_url=sess.get("github_url"),
        created_at=sess.get("created_at"),
    )


@router.delete("/session/{session_id}")
def delete_session(session_id: str):
    if session_id not in ide_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    sess = ide_sessions[session_id]
    sandbox: IDESandbox = sess["sandbox"]

    try:
        sandbox.cleanup()
    except Exception as e:
        logger.warning(f"Cleanup error for session {session_id}: {e}")

    sess["status"] = "stopped"
    del ide_sessions[session_id]

    return {"message": "Session stopped", "session_id": session_id}


@router.get("/session/{session_id}/files")
def list_files(session_id: str, path: str = Query(default="/testbed")):
    sandbox = _get_sandbox(session_id)
    files = sandbox.list_files(path)
    return {"path": path, "files": files}


@router.get("/session/{session_id}/file")
def read_file(session_id: str, path: str = Query(...)):
    sandbox = _get_sandbox(session_id)
    content = sandbox.read_file(path)
    if content is None:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return {"path": path, "content": content}


@router.put("/session/{session_id}/file")
def write_file(session_id: str, body: FileWriteRequest):
    sandbox = _get_sandbox(session_id)
    sandbox.write_file(body.path, body.content)
    return {"path": body.path, "message": "File saved"}


@router.websocket("/terminal/ws/{session_id}")
async def terminal_websocket(websocket: WebSocket, session_id: str):
    if session_id not in ide_sessions:
        await websocket.close(code=4004, reason="Session not found")
        return

    sandbox: IDESandbox = ide_sessions[session_id]["sandbox"]

    await websocket.accept()
    logger.info(f"Terminal WebSocket connected for session {session_id}")

    try:
        exec_id, sock = sandbox.create_exec_shell()

        # Get the raw socket for reading
        raw_socket = sock._sock

        async def docker_to_ws():
            loop = asyncio.get_event_loop()
            try:
                while True:
                    data = await loop.run_in_executor(None, raw_socket.recv, 4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
            except Exception as e:
                logger.debug(f"docker_to_ws ended: {e}")

        async def ws_to_docker():
            loop = asyncio.get_event_loop()
            try:
                while True:
                    data = await websocket.receive_bytes()
                    sandbox.touch()
                    await loop.run_in_executor(None, raw_socket.sendall, data)
            except WebSocketDisconnect:
                logger.info(f"Terminal WebSocket disconnected for session {session_id}")
            except Exception as e:
                logger.debug(f"ws_to_docker ended: {e}")

        await asyncio.gather(docker_to_ws(), ws_to_docker())

    except Exception as e:
        logger.error(f"Terminal WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info(f"Terminal WebSocket closed for session {session_id}")


def _get_sandbox(session_id: str) -> IDESandbox:
    if session_id not in ide_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    sess = ide_sessions[session_id]
    if sess["status"] != "running":
        raise HTTPException(status_code=400, detail="Session is not running")

    sandbox: IDESandbox = sess["sandbox"]
    sandbox.touch()
    return sandbox

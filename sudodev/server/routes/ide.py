import uuid
import asyncio
import threading
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from pydantic import BaseModel

from sudodev.runtime.ide_sandbox import IDESandbox
from sudodev.core.utils.logger import setup_logger
from sudodev.core.agent_observer import BaseAgentObserver, AgentEvent
from sudodev.core.unified_agent import UnifiedAgent

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
        terminal_id, terminal = sandbox.create_exec_shell()

        async def e2b_to_ws():
            """Forward E2B terminal output to WebSocket."""
            loop = asyncio.get_event_loop()
            try:
                while True:
                    data = await loop.run_in_executor(None, lambda: terminal.read(timeout=1))
                    if data:
                        await websocket.send_text(data)
            except Exception as e:
                logger.debug(f"e2b_to_ws ended: {e}")

        async def ws_to_e2b():
            """Forward WebSocket input to E2B terminal."""
            try:
                while True:
                    raw = await websocket.receive()
                    sandbox.touch()

                    # Phase 6: Handle ping/pong keep-alive
                    if "text" in raw:
                        try:
                            msg = json.loads(raw["text"])
                            if msg.get("type") == "ping":
                                await websocket.send_json({"type": "pong"})
                                continue
                        except (json.JSONDecodeError, TypeError):
                            pass
                        terminal.send_data(raw["text"])
                    elif "bytes" in raw:
                        terminal.send_data(raw["bytes"].decode("utf-8", errors="replace"))
            except WebSocketDisconnect:
                logger.info(f"Terminal WebSocket disconnected for session {session_id}")
            except Exception as e:
                logger.debug(f"ws_to_e2b ended: {e}")

        await asyncio.gather(e2b_to_ws(), ws_to_e2b())

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


class WebSocketAgentObserver(BaseAgentObserver):
    def __init__(self, websocket: WebSocket, loop: asyncio.AbstractEventLoop):
        self.ws = websocket
        self.loop = loop
        self._user_reply_future: Optional[asyncio.Future] = None

    def _send(self, event_type: str, data: dict):
        event = AgentEvent(type=event_type, data=data).model_dump_json()
        asyncio.run_coroutine_threadsafe(self.ws.send_text(event), self.loop)

    def on_step(self, name: str, description: str) -> None:
        super().on_step(name, description)
        self._send('step', {'name': name, 'description': description})

    def on_log(self, message: str) -> None:
        super().on_log(message)
        self._send('log', {'message': message})

    def on_highlight(self, filepath: str, lines: Optional[str] = None) -> None:
        super().on_highlight(filepath, lines)
        self._send('highlight', {'filepath': filepath, 'lines': lines})

    def ask_user(self, prompt: str) -> str:
        super().ask_user(prompt)
        future = asyncio.run_coroutine_threadsafe(self._ask_user_async(prompt), self.loop)
        return future.result()

    async def _ask_user_async(self, prompt: str) -> str:
        self._user_reply_future = self.loop.create_future()
        event = AgentEvent(type='ask_user', data={'prompt': prompt}).model_dump_json()
        await self.ws.send_text(event)
        reply = await self._user_reply_future
        self._user_reply_future = None
        return reply

    def resolve_user_reply(self, reply: str):
        if self._user_reply_future and not self._user_reply_future.done():
            self._user_reply_future.set_result(reply)

@router.websocket("/agent/ws/{session_id}")
async def agent_websocket(websocket: WebSocket, session_id: str):
    if session_id not in ide_sessions:
        await websocket.close(code=4004, reason="Session not found")
        return

    sess = ide_sessions[session_id]
    await websocket.accept()
    logger.info(f"Agent WebSocket connected for session {session_id}")

    loop = asyncio.get_event_loop()
    observer = WebSocketAgentObserver(websocket, loop)
    agent_thread = None

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "start":
                if agent_thread and agent_thread.is_alive():
                    continue
                
                # Retrieve the initial issue context if we have one
                issue_description = sess.get("problem_statement", "Fix the issue according to the repository context.")

                def run_agent():
                    try:
                        agent = UnifiedAgent(
                            mode=sess["mode"],
                            issue_data={
                                "instance_id": sess.get("instance_id"),
                                "problem_statement": issue_description
                            },
                            github_url=sess.get("github_url"),
                            branch=sess.get("branch", "main"),
                            issue_description=issue_description,
                            observer=observer,
                            sandbox=sess["sandbox"]
                        )
                        success = agent.run()
                        observer._send('done', {'success': success})
                    except Exception as e:
                        logger.error(f"Agent thread error: {e}")
                        import traceback
                        traceback.print_exc()
                        observer._send('error', {'message': str(e)})

                agent_thread = threading.Thread(target=run_agent, daemon=True)
                agent_thread.start()

            elif action == "reply":
                reply_text = data.get("text", "")
                observer.resolve_user_reply(reply_text)

    except WebSocketDisconnect:
        logger.info(f"Agent WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"Agent WebSocket error: {e}")

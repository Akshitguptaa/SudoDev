from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sudodev.db.models import AgentRun, IDESession


async def create_run(
    db: AsyncSession,
    run_id: str,
    mode: str,
    instance_id: Optional[str] = None,
    github_url: Optional[str] = None,
    problem_statement: Optional[str] = None,
) -> AgentRun:
    run = AgentRun(
        id=run_id,
        mode=mode,
        instance_id=instance_id,
        github_url=github_url,
        problem_statement=problem_statement,
        status="pending",
        logs=[],
        patch="",
        message="Initializing...",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def get_run(db: AsyncSession, run_id: str) -> Optional[AgentRun]:
    result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
    return result.scalar_one_or_none()


async def update_run_status(
    db: AsyncSession,
    run_id: str,
    status: str,
    message: Optional[str] = None,
    patch: Optional[str] = None,
) -> Optional[AgentRun]:
    run = await get_run(db, run_id)
    if not run:
        return None
    run.status = status
    if message is not None:
        run.message = message
    if patch is not None:
        run.patch = patch
    await db.commit()
    await db.refresh(run)
    return run


async def append_log(
    db: AsyncSession,
    run_id: str,
    log_message: str,
    step: Optional[int] = None,
) -> Optional[AgentRun]:
    run = await get_run(db, run_id)
    if not run:
        return None
    current_logs = list(run.logs) if run.logs else []
    current_logs.append(log_message)
    run.logs = current_logs
    if step is not None:
        run.current_step = step
    await db.commit()
    await db.refresh(run)
    return run


async def list_runs(db: AsyncSession) -> list[AgentRun]:
    result = await db.execute(select(AgentRun).order_by(AgentRun.created_at.desc()))
    return list(result.scalars().all())


async def create_ide_session(
    db: AsyncSession,
    session_id: str,
    mode: str,
    instance_id: Optional[str] = None,
    github_url: Optional[str] = None,
    run_id: Optional[str] = None,
) -> IDESession:
    session = IDESession(
        id=session_id,
        run_id=run_id,
        mode=mode,
        instance_id=instance_id,
        github_url=github_url,
        status="running",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_ide_session(db: AsyncSession, session_id: str) -> Optional[IDESession]:
    result = await db.execute(select(IDESession).where(IDESession.id == session_id))
    return result.scalar_one_or_none()


async def delete_ide_session(db: AsyncSession, session_id: str) -> bool:
    session = await get_ide_session(db, session_id)
    if not session:
        return False
    await db.delete(session)
    await db.commit()
    return True

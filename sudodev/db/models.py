import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sudodev.db.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, nullable=False, default="pending")
    mode = Column(String, nullable=False)
    instance_id = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    problem_statement = Column(Text, nullable=True)
    message = Column(Text, nullable=True, default="Initializing...")
    current_step = Column(Integer, default=0)
    patch = Column(Text, default="")
    logs = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    ide_sessions = relationship("IDESession", back_populates="agent_run")


class IDESession(Base):
    __tablename__ = "ide_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("agent_runs.id"), nullable=True)
    status = Column(String, nullable=False, default="running")
    mode = Column(String, nullable=True)
    instance_id = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    agent_run = relationship("AgentRun", back_populates="ide_sessions")

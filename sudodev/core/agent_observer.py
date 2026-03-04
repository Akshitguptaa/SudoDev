from typing import Optional, Protocol
import asyncio
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class AgentEvent(BaseModel):
    type: str # 'step', 'log', 'highlight', 'ask_user', 'done', 'error'
    data: dict

class AgentObserver(Protocol):
    """Interface for observing and interacting with an agent run."""
    
    def on_step(self, name: str, description: str) -> None:
        ...
        
    def on_log(self, message: str) -> None:
        ...
        
    def on_highlight(self, filepath: str, lines: Optional[str] = None) -> None:
        ...
        
    def ask_user(self, prompt: str) -> str:
        ...


class BaseAgentObserver:
    def on_step(self, name: str, description: str) -> None:
        logger.info(f"Starting {name.lower()}: {description}")
        
    def on_log(self, message: str) -> None:
        logger.info(f"Agent: {message}")
        
    def on_highlight(self, filepath: str, lines: Optional[str] = None) -> None:
        logger.info(f"Agent highlights: {filepath} {lines or ''}")
        
    def ask_user(self, prompt: str) -> str:
        logger.warning(f"Agent asked a question but no interactive observer is attached: {prompt}")
        return "Not available in headless mode."

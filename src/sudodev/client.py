import os
from groq import Groq
from sudodev.utils.logger import setup_logger

logger = setup_logger(__name__)

class LLMClient:
    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"

    def get_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        return "res"
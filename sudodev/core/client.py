import os
from google import genai
from google.genai import types
from sudodev.core.utils.logger import setup_logger

logger = setup_logger(__name__)


class LLMClient:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("environment variable not set")

        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.0-flash"

    def get_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 8192, conversation_history: list = None) -> str:
        try:
            contents = []

            if conversation_history:
                for msg in conversation_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    gemini_role = "model" if role == "assistant" else "user"
                    contents.append(types.Content(role=gemini_role, parts=[types.Part(text=content)]))

            contents.append(types.Content(role="user", parts=[types.Part(text=user_prompt)]))

            logger.info(f"sending request to {self.model_name} (temp={temperature}, max_tokens={max_tokens})")

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
                top_p=1.0,
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )

            result = response.text
            logger.info(f"received response ({len(result)} chars)")

            return result
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise

    def get_completion_with_retry(self, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 8192, max_retries: int = 3) -> str:
        import time
        for attempt in range(max_retries):
            try:
                return self.get_completion(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} attempts failed.")
                    raise

    def get_structured_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        enhanced_system = system_prompt + "\n Respond in a clear, structured format."
        return self.get_completion(
            system_prompt=enhanced_system,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=8192
        )
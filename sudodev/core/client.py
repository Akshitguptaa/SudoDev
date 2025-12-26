import os
from groq import Groq
from sudodev.core.utils.logger import setup_logger

logger = setup_logger(__name__)

class LLMClient:
    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"

    def get_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 4096, conversation_history: list = None) -> str:
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_prompt})

            logger.info(f"sending request to {self.model} (temp = {temperature}, max_tokens = {max_tokens})")
            logger.debug(f"user prompt preview: {user_prompt[:100]} ...")

            response = self.client.chat.completions.create(
                model = self.model,
                messages = messages,
                temperature = temperature, 
                max_tokens = max_tokens,
                top_p = 1,
                stream = False
            )

            result = response.choices[0].message.content
            logger.info(f"received response ({len(result)} chars)")
            logger.debug(f"response preview: {result[:100]}...")

            return result
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise
    
    def get_completion_with_retry(
            self,
            system_prompt: str,
            user_prompt: str,
            temperature: float = 0.2,
            max_tokens: int = 4096,
            max_retries: int = 3
    ) -> str:
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
                if attempt < max_retries-1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Attemp t {attempt + 1} failed: {e}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error("all {max_retries} attempts failed.")
                    raise


    def get_structured_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        enhanced_system = system_prompt + "\n Respond in a clear, structured format."
        return self.get_completion(
            system_prompt=enhanced_system,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=4096
        )
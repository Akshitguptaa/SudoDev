import os

GROQ = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("LLM")
SANDBOX_TIMEOUT = 120
WORK_DIR = "/testbed"
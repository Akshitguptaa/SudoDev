import os
from dotenv import load_dotenv

load_dotenv()

GROQ = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("LLM")
SANDBOX_TIMEOUT = int(120)
WORK_DIR = "/testbed"
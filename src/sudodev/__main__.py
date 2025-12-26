import os
import sys
from dotenv import load_dotenv
from datasets import load_dataset
from sudodev.agent import Agent
from sudodev.improved_agent import ImprovedAgent
from sudodev.utils.logger import setup_logger

def main():
    load_dotenv()
    logger = setup_logger()
    
    if not os.environ.get("GROQ_API_KEY"):
        logger.error("env file issue add api")
        sys.exit(1)

    logger.info("Loading dataset...")
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    instance_id = "django__django-11001" # Placeholder target
    
    issue = next((item for item in dataset if item["instance_id"] == instance_id), None)
    if not issue:
        logger.error("Issue not found.")
        sys.exit(1)

    logger.info(f"Starting agent on {instance_id}")
    agent = ImprovedAgent(issue)
    success = agent.run()

    if success:
        logger.info("Agent completed successfully")
    else:
        logger.error("Agent failed to resolve issue")

if __name__ == "__main__":
    main()
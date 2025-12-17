from sudodev.client import LLMClient
from sudodev.sandbox.container import Sandbox
from sudodev.utils.logger import log_step, setup_logger

logger = setup_logger(__name__)

SYSTEM_PROMPT = """ test """

class Agent:

    def __init__(self, issue_data):
        self.issue = issue_data
        self.llm = LLMClient()
        self.sandbox = Sandbox(issue_data['instance_id'])

    def run(self):
        # Reproduce -> Fix -> Verify

        log_step("INIT", f"Starting run for {self.issue['instance_id']}")
        
        try:
            self.sandbox.start()
            #agent logic loop 
            pass

        except Exception as e:
            logger.critical(f"Agent failed: {e}")
        finally:
            self.sandbox.cleanup()

    def _reproduce_bug(self):
        pass

    def _generate_fix(self):
        pass

    def _verify_fix(self):
        pass
from sudodev.core.improved_agent import ImprovedAgent
from sudodev.runtime.github_sandbox import GitHubSandbox
from sudodev.core.utils.logger import setup_logger

logger = setup_logger(__name__)

class UnifiedAgent:
    def __init__(self, mode: str, **kwargs):
        self.mode = mode

        if mode == "swebench":
            self.issue = kwargs['issue_data']
            self.agent = ImprovedAgent(self.issue)
            logger.info(f"Initialized SWE-bench agent for {self.issue['instance_id']}")
        
        elif mode == "github":
            github_url = kwargs['github_url']
            branch = kwargs.get('branch', 'main')
            issue_description = kwargs.get('issue_description', '')
            repo_name = kwargs.get('repo_name', 'custom')

            self.issue = {
                'instance_id': f"github-{repo_name}",
                'problem_statement': issue_description,
                'repo': github_url,
                'branch': branch
            }

            logger.info(f"Initializing GitHub agent for {github_url} (branch: {branch})")

            self.agent = ImprovedAgent(self.issue)
            self.agent.sandbox = GitHubSandbox(github_url, branch)
            logger.info("GitHub sandbox configured")
        
        else:
            raise ValueError(f"Unknown mode: {mode}. Must be 'swebench' or 'github'")
        
    def run(self):
        logger.info(f"Starting agent run in {self.mode} mode")
        try:
            success = self.agent.run()
            logger.info(f"Agent run {'succeeded' if success else 'failed'}")
            return success
        except Exception as e:
            logger.error(f"Agent run failed with error: {e}")
            raise

    def get_patch(self):
        if hasattr(self.agent, 'get_patch'):
            return self.agent.get_patch()
        return ""
    
    
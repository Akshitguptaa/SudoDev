import os
import time
from e2b_code_interpreter import Sandbox as E2BSandboxSDK
from sudodev.core.utils.logger import setup_logger

logger = setup_logger(__name__)


class GitHubSandbox:
    """Sandbox for arbitrary GitHub repositories using E2B cloud microVMs."""

    def __init__(self, github_url: str, branch: str = "main"):
        self.github_url = github_url
        self.branch = branch
        self.sandbox = None
        self.repo_name = self._extract_repo_name(github_url)
        self.template_id = os.getenv("E2B_TEMPLATE_ID", "base")
        self.api_key = os.getenv("E2B_API_KEY")

    def _extract_repo_name(self, url: str) -> str:
        parts = url.rstrip('/').split('/')
        if parts[-1].endswith('.git'):
            parts[-1] = parts[-1][:-4]
        return f"{parts[-2]}-{parts[-1]}".lower()

    def start(self):
        """Start an E2B sandbox and clone the repository."""
        try:
            logger.info(f"Starting E2B sandbox for {self.github_url}...")
            self.sandbox = E2BSandboxSDK(
                template=self.template_id,
                api_key=self.api_key,
            )
            logger.info(f"E2B sandbox started (ID: {self.sandbox.sandbox_id})")

            # Clone the repository
            logger.info(f"Cloning {self.github_url} (branch: {self.branch})...")
            clone_result = self.sandbox.commands.run(
                f"git clone --depth 1 --branch {self.branch} {self.github_url} /testbed",
                timeout=120,
            )
            if clone_result.exit_code != 0:
                logger.error(f"Clone failed: {clone_result.stderr}")
                raise RuntimeError(f"Failed to clone repo: {clone_result.stderr}")

            # Install dependencies
            logger.info("Installing dependencies...")
            self.sandbox.commands.run(
                "cd /testbed && "
                "if [ -f requirements.txt ]; then pip install -r requirements.txt 2>&1 || true; fi && "
                "if [ -f setup.py ]; then pip install -e . 2>&1 || true; fi && "
                "if [ -f pyproject.toml ]; then pip install -e . 2>&1 || true; fi && "
                "if [ -f package.json ]; then npm install 2>&1 || true; fi",
                timeout=180,
            )
            logger.info("Dependencies installed")

            return True

        except Exception as e:
            logger.error(f"Failed to start E2B sandbox: {e}")
            return False

    def run_command(self, cmd: str, timeout: int = 60):
        """Run command in the E2B sandbox."""
        if not self.sandbox:
            raise RuntimeError("Sandbox is not running.")

        try:
            result = self.sandbox.commands.run(
                cmd,
                timeout=timeout,
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            output = stdout + stderr
            return result.exit_code, output
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return -1, str(e)

    def write_file(self, filepath: str, content: str):
        """Write file to the E2B sandbox."""
        if not self.sandbox:
            raise RuntimeError("Sandbox is not running.")

        if not filepath.startswith("/"):
            filepath = f"/testbed/{filepath}"

        self.sandbox.files.write(filepath, content)
        logger.info(f"Wrote file: {filepath}")

    def read_file(self, filepath: str) -> str:
        """Read file from the E2B sandbox."""
        if not self.sandbox:
            raise RuntimeError("Sandbox is not running.")

        if not filepath.startswith("/"):
            filepath = f"/testbed/{filepath}"

        try:
            content = self.sandbox.files.read(filepath)
            return content
        except Exception as e:
            logger.warning(f"Read file failed for {filepath}: {e}")
            return None

    def cleanup(self):
        """Clean up the E2B sandbox."""
        if self.sandbox:
            try:
                self.sandbox.kill()
                logger.info("E2B sandbox cleaned up")
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")
            finally:
                self.sandbox = None

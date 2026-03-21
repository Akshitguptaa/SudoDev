import os
import time
from e2b_code_interpreter import Sandbox as E2BSandboxSDK
from sudodev.core.utils.logger import setup_logger

logger = setup_logger(__name__)


class IDESandbox:
    """
    Interactive sandbox for Web IDE sessions.
    Uses E2B cloud microVMs instead of local Docker containers.
    """

    def __init__(self, mode: str, instance_id: str = None,
                 github_url: str = None, branch: str = "main"):
        self.mode = mode
        self.instance_id = instance_id
        self.github_url = github_url
        self.branch = branch
        self.sandbox = None
        self.template_id = os.getenv("E2B_TEMPLATE_ID", "base")
        self.api_key = os.getenv("E2B_API_KEY")
        self.created_at = time.time()
        self.last_activity = time.time()

    def start(self):
        logger.info(f"Starting E2B IDE sandbox (mode={self.mode})...")
        self.sandbox = E2BSandboxSDK(
            template=self.template_id,
            api_key=self.api_key,
        )
        logger.info(f"E2B IDE sandbox started (ID: {self.sandbox.sandbox_id})")

        # Set up the working environment
        self.sandbox.commands.run("mkdir -p /testbed")

        if self.mode == "github" and self.github_url:
            logger.info(f"Cloning {self.github_url} (branch: {self.branch})...")
            clone_result = self.sandbox.commands.run(
                f"git clone --depth 1 --branch {self.branch} {self.github_url} /testbed",
                timeout=120,
            )
            if clone_result.exit_code != 0:
                logger.error(f"Clone failed: {clone_result.stderr}")
                raise RuntimeError(f"Failed to clone repo: {clone_result.stderr}")
            logger.info("Repository cloned successfully")

            # Install dependencies
            self.sandbox.commands.run(
                "cd /testbed && "
                "if [ -f requirements.txt ]; then pip install -r requirements.txt 2>&1 || true; fi && "
                "if [ -f setup.py ]; then pip install -e . 2>&1 || true; fi && "
                "if [ -f pyproject.toml ]; then pip install -e . 2>&1 || true; fi && "
                "if [ -f package.json ]; then npm install 2>&1 || true; fi",
                timeout=180,
            )
            logger.info("Dependencies installed")

        self.last_activity = time.time()
        return True

    def touch(self):
        self.last_activity = time.time()

    def is_idle(self, timeout_seconds: int = 1800) -> bool:
        return (time.time() - self.last_activity) > timeout_seconds

    def list_files(self, path: str = "/testbed") -> list:
        if not self.sandbox:
            raise RuntimeError("Sandbox is not running.")

        self.touch()
        exit_code, output = self._exec(f"ls -la --group-directories-first {path}")
        if exit_code != 0:
            return []

        entries = []
        for line in output.strip().split("\n")[1:]:  # Skip "total" line
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue

            name = parts[8]
            if name in (".", ".."):
                continue

            is_dir = parts[0].startswith("d")
            size = int(parts[4]) if not is_dir else 0
            entries.append({
                "name": name,
                "path": os.path.join(path, name),
                "is_dir": is_dir,
                "size": size,
                "permissions": parts[0],
            })

        return entries

    def read_file(self, filepath: str) -> str:
        if not self.sandbox:
            raise RuntimeError("Sandbox is not running.")

        self.touch()
        if not filepath.startswith("/"):
            filepath = f"/testbed/{filepath}"

        try:
            content = self.sandbox.files.read(filepath)
            return content
        except Exception as e:
            logger.warning(f"Read file failed for {filepath}: {e}")
            return None

    def write_file(self, filepath: str, content: str):
        if not self.sandbox:
            raise RuntimeError("Sandbox is not running.")

        self.touch()
        if not filepath.startswith("/"):
            filepath = f"/testbed/{filepath}"

        self.sandbox.files.write(filepath, content)
        logger.info(f"Wrote file: {filepath}")

    def run_command(self, cmd: str, timeout: int = 60):
        if not self.sandbox:
            raise RuntimeError("Sandbox is not running.")

        self.touch()
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
            return -1, str(e)

    def _exec(self, cmd: str):
        result = self.sandbox.commands.run(cmd)
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        return result.exit_code, stdout + stderr

    def create_exec_shell(self):
        """
        Create an interactive terminal session via E2B.
        Returns a tuple of (terminal_id, terminal) for WebSocket bridging.
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox is not running.")

        self.touch()
        terminal = self.sandbox.terminals.start(
            cols=120,
            rows=40,
            cwd="/testbed",
        )
        return terminal.terminal_id, terminal

    def cleanup(self):
        if self.sandbox:
            try:
                self.sandbox.kill()
                logger.info("E2B IDE sandbox cleaned up")
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")
            finally:
                self.sandbox = None

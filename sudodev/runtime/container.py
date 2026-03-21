import os
from e2b_code_interpreter import Sandbox as E2BSandboxSDK
from sudodev.core.utils.logger import setup_logger

logger = setup_logger(__name__)


class Sandbox:
    def __init__(self, instance_id: str):
        self.instance_id = instance_id
        self.template_id = os.getenv("E2B_TEMPLATE_ID", "base")
        self.api_key = os.getenv("E2B_API_KEY")
        self.sandbox = None

    def start(self):
        try:
            logger.info(f"Starting E2B sandbox for {self.instance_id}...")
            self.sandbox = E2BSandboxSDK(
                template=self.template_id,
                api_key=self.api_key,
            )
            logger.info(f"E2B sandbox started (ID: {self.sandbox.sandbox_id})")

            # Set up testbed directory
            self.sandbox.commands.run("mkdir -p /testbed")
        except Exception as e:
            logger.error(f"Failed to start E2B sandbox: {e}")
            raise

    def run_command(self, cmd: str, timeout: int = 60):
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
            return -1, str(e)

    def write_file(self, filepath: str, content: str):
        if not self.sandbox:
            raise RuntimeError("Sandbox is not running.")

        if not filepath.startswith("/"):
            filepath = f"/testbed/{filepath}"

        self.sandbox.files.write(filepath, content)

    def read_file(self, filepath: str) -> str:
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
        if self.sandbox:
            try:
                self.sandbox.kill()
                logger.info("E2B sandbox cleaned up.")
            except Exception as e:
                logger.warning(f"E2B cleanup error: {e}")
            finally:
                self.sandbox = None

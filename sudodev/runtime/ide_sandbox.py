import docker
import tarfile
import io
import os
import time
import threading
import asyncio
from sudodev.core.utils.logger import setup_logger

logger = setup_logger(__name__)


class IDESandbox:
    """
    Interactive sandbox for Web IDE sessions.
    Keeps a Docker container alive for interactive file browsing,
    editing, and terminal access.
    """

    def __init__(self, mode: str, instance_id: str = None,
                 github_url: str = None, branch: str = "main"):
        self.client = docker.from_env()
        self.mode = mode
        self.instance_id = instance_id
        self.github_url = github_url
        self.branch = branch
        self.container = None
        self.image_name = None
        self.created_at = time.time()
        self.last_activity = time.time()
        self._pty_exec = None

    def _find_swebench_image(self, instance_id: str) -> str:
        """Find SWE-bench Docker image by instance ID."""
        try:
            images = self.client.images.list()
            issue_part = instance_id.split("__")[-1] if "__" in instance_id else instance_id

            for img in images:
                for tag in img.tags:
                    if issue_part in tag and "sweb.eval" in tag:
                        logger.info(f"Found image for {instance_id}: {tag}")
                        return tag

            logger.warning(f"Image not found for {instance_id}, using default format")
            return f"sweb.eval.x86_64.{instance_id}"
        except Exception as e:
            logger.error(f"Error searching for image: {e}")
            return f"sweb.eval.x86_64.{instance_id}"

    def _build_github_image(self) -> str:
        """Build a Docker image for a GitHub repository."""
        parts = self.github_url.rstrip('/').split('/')
        repo_name = parts[-1].replace('.git', '')
        owner = parts[-2]
        image_name = f"sudodev-ide-{owner}-{repo_name}:latest".lower()

        # Check if image already exists
        try:
            self.client.images.get(image_name)
            logger.info(f"Using existing image: {image_name}")
            return image_name
        except docker.errors.ImageNotFound:
            pass

        dockerfile_content = f"""
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \\
    git \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \\
    && apt-get install -y nodejs \\
    && rm -rf /var/lib/apt/lists/* \\
    || echo "Node.js install skipped"

WORKDIR /testbed

RUN git clone --depth 1 --branch {self.branch} {self.github_url} /testbed

RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt 2>&1 || true; fi
RUN if [ -f setup.py ]; then pip install --no-cache-dir -e . 2>&1 || true; fi
RUN if [ -f pyproject.toml ]; then pip install --no-cache-dir -e . 2>&1 || true; fi
RUN if [ -f package.json ]; then npm install 2>&1 || true; fi

CMD ["/bin/bash"]
"""
        logger.info(f"Building Docker image {image_name}...")
        image, build_logs = self.client.images.build(
            fileobj=io.BytesIO(dockerfile_content.encode()),
            tag=image_name,
            rm=True
        )
        logger.info(f"Successfully built image: {image_name}")
        return image_name

    def start(self):
        if self.mode == "swebench":
            self.image_name = self._find_swebench_image(self.instance_id)
        elif self.mode == "github":
            self.image_name = self._build_github_image()
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

        logger.info(f"Starting IDE container from {self.image_name}...")
        self.container = self.client.containers.run(
            self.image_name,
            command="tail -f /dev/null",
            detach=True,
            working_dir="/testbed",
            user="root",
            stdin_open=True,
            tty=True,
        )
        logger.info(f"IDE container started (ID: {self.container.short_id})")
        time.sleep(2)
        self.last_activity = time.time()
        return True

    def touch(self):
        self.last_activity = time.time()

    def is_idle(self, timeout_seconds: int = 1800) -> bool:
        return (time.time() - self.last_activity) > timeout_seconds

    def list_files(self, path: str = "/testbed") -> list:
        if not self.container:
            raise RuntimeError("Container is not running.")

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
        if not self.container:
            raise RuntimeError("Container is not running.")

        self.touch()
        if not filepath.startswith("/"):
            filepath = f"/testbed/{filepath}"

        try:
            bits, _ = self.container.get_archive(filepath)
            file_obj = io.BytesIO()
            for chunk in bits:
                file_obj.write(chunk)
            file_obj.seek(0)

            with tarfile.open(fileobj=file_obj) as tar:
                member = tar.next()
                f = tar.extractfile(member)
                return f.read().decode('utf-8')
        except Exception as e:
            logger.warning(f"Read file failed for {filepath}: {e}")
            return None

    def write_file(self, filepath: str, content: str):
        if not self.container:
            raise RuntimeError("Container is not running.")

        self.touch()
        if not filepath.startswith("/"):
            filepath = f"/testbed/{filepath}"

        # Split into directory and filename
        dir_path = os.path.dirname(filepath)
        filename = os.path.basename(filepath)

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            data = content.encode('utf-8')
            info = tarfile.TarInfo(name=filename)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        tar_stream.seek(0)
        self.container.put_archive(path=dir_path, data=tar_stream)
        logger.info(f"Wrote file: {filepath}")

    def _exec(self, cmd: str):
        exec_result = self.container.exec_run(
            ["/bin/bash", "-c", cmd],
            workdir="/testbed"
        )
        output = exec_result.output.decode('utf-8', errors='replace')
        return exec_result.exit_code, output

    def create_exec_shell(self):
        if not self.container:
            raise RuntimeError("Container is not running.")

        self.touch()
        # Use the Docker API to create an exec instance with PTY
        exec_instance = self.client.api.exec_create(
            self.container.id,
            cmd="/bin/bash",
            stdin=True,
            tty=True,
            stdout=True,
            stderr=True,
            workdir="/testbed",
        )
        sock = self.client.api.exec_start(
            exec_instance['Id'],
            socket=True,
            tty=True,
        )
        return exec_instance['Id'], sock

    def cleanup(self):
        if self.container:
            try:
                self.container.stop(timeout=5)
                self.container.remove()
                logger.info(f"IDE container cleaned up: {self.container.short_id}")
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")
            finally:
                self.container = None

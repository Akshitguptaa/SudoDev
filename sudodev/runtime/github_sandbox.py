import docker
import tarfile
import io
import time
from sudodev.core.utils.logger import setup_logger

logger = setup_logger(__name__)

class GitHubSandbox:
    """Sandbox for arbitrary GitHub repositories"""
    
    def __init__(self, github_url: str, branch: str = "main"):
        self.client = docker.from_env()
        self.github_url = github_url
        self.branch = branch
        self.container = None
        self.repo_name = self._extract_repo_name(github_url)
        self.image_name = f"sudodev-github-{self.repo_name}:latest"
        
    def _extract_repo_name(self, url: str) -> str:
        parts = url.rstrip('/').split('/')
        if parts[-1].endswith('.git'):
            parts[-1] = parts[-1][:-4]
        return f"{parts[-2]}-{parts[-1]}".lower()
    
    def build_image(self):
        """Build Docker image with the GitHub repo"""
        logger.info(f"Building Docker image for {self.github_url}...")
        
        # Create Dockerfile content
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

# Clone the repository
RUN git clone --depth 1 --branch {self.branch} {self.github_url} /testbed

# Install dependencies in order of priority
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt 2>&1 || true; fi
RUN if [ -f setup.py ]; then pip install --no-cache-dir -e . 2>&1 || true; fi
RUN if [ -f pyproject.toml ]; then pip install --no-cache-dir -e . 2>&1 || true; fi
RUN if [ -f package.json ]; then npm install 2>&1 || true; fi

CMD ["/bin/bash"]
"""
        
        # Build image
        try:
            logger.info("Starting Docker image build (this may take a few minutes)...")
            image, build_logs = self.client.images.build(
                fileobj=io.BytesIO(dockerfile_content.encode()),
                tag=self.image_name,
                rm=True
            )
            
            # Process build logs
            if build_logs:
                for log_line in build_logs:
                    if isinstance(log_line, dict):
                        if 'stream' in log_line:
                            msg = log_line['stream'].strip()
                            if msg:
                                logger.info(msg)
                        elif 'error' in log_line:
                            logger.error(log_line['error'].strip())
                    elif isinstance(log_line, str):
                        logger.info(log_line.strip())
            
            logger.info(f"Successfully built image: {self.image_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def start(self):
        """Start the container"""
        try:
            # Check if image exists, build if not
            try:
                self.client.images.get(self.image_name)
                logger.info(f"Using existing image: {self.image_name}")
            except docker.errors.ImageNotFound:
                logger.info("Image not found, building...")
                if not self.build_image():
                    raise RuntimeError("Failed to build Docker image")
            
            logger.info(f"Starting container from {self.image_name}...")
            self.container = self.client.containers.run(
                self.image_name,
                command="tail -f /dev/null",
                detach=True,
                working_dir="/testbed",
                user="root"
            )
            logger.info(f"Container started (ID: {self.container.short_id})")
            time.sleep(2)
            return True
            
        except Exception as e:
            logger.error(f"Failed to start container: {e}")
            return False
    
    def run_command(self, cmd: str, timeout: int = 60):
        """Run command in container"""
        if not self.container:
            raise RuntimeError("Container is not running.")
        
        wrapped_cmd = f"/bin/bash -c '{cmd}'"
        
        try:
            exec_result = self.container.exec_run(
                ["/bin/bash", "-c", cmd],
                workdir="/testbed"
            )
            output = exec_result.output.decode('utf-8', errors='replace')
            return exec_result.exit_code, output
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return -1, str(e)
    
    def write_file(self, filepath: str, content: str):
        """Write file to container"""
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            data = content.encode('utf-8')
            info = tarfile.TarInfo(name=filepath)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        
        tar_stream.seek(0)
        self.container.put_archive(path="/testbed", data=tar_stream)
        logger.info(f"Wrote file: {filepath}")
    
    def read_file(self, filepath: str) -> str:
        """Read file from container"""
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
    
    def cleanup(self):
        """Clean up container and optionally image"""
        if self.container:
            try:
                self.container.stop()
                self.container.remove()
                logger.info("Container cleaned up")
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")
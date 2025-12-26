import docker
import tarfile
import io
import time
from sudodev.core.utils.logger import setup_logger

logger = setup_logger(__name__)

class Sandbox:
    def __init__(self, instance_id: str):
        self.client = docker.from_env()
        self.instance_id = instance_id
        self.image_name = self._find_image_name(instance_id)
        self.container = None

    def _find_image_name(self, instance_id):
        try:
            images = self.client.images.list()
            search_term = instance_id.split("__")[-1] if "__" in instance_id else instance_id
            for img in images:
                for tag in img.tags:
                    if search_term in tag and "sweb.eval" in tag:
                        return tag
            return f"sweb.eval.x86_64.{instance_id}"
        except Exception:
            return f"sweb.eval.x86_64.{instance_id}"

    def start(self):
        try:
            logger.info(f"Attempting to start sandbox for {self.image_name}...")
            self.container = self.client.containers.run(
                self.image_name,
                command="tail -f /dev/null", 
                detach=True,
                working_dir="/testbed",
                user="root" 
            )
            logger.info(f"Sandbox started (ID: {self.container.short_id})")
            time.sleep(2)
        except docker.errors.ImageNotFound:
            logger.error(f"Docker image '{self.image_name}' not found.")
            raise

    def run_command(self, cmd: str, timeout: int = 60):
        if not self.container:
            raise RuntimeError("Container is not running.")

        wrapped_cmd = f"/bin/bash -c 'source ~/.bashrc && {cmd}'"
        
        try:
            exec_result = self.container.exec_run(
                wrapped_cmd,
                workdir="/testbed"
            )
            output = exec_result.output.decode('utf-8', errors='replace')
            return exec_result.exit_code, output
        except Exception as e:
            return -1, str(e)

    def write_file(self, filepath: str, content: str):
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            data = content.encode('utf-8')
            info = tarfile.TarInfo(name=filepath)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        
        tar_stream.seek(0)
        self.container.put_archive(path="/testbed", data=tar_stream)

    def read_file(self, filepath: str) -> str:
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
        if self.container:
            self.container.stop()
            self.container.remove()
            logger.info("Sandbox container cleaned up.")
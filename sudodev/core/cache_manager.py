import os
import json
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class InstanceCacheManager:

    def __init__(self, cache_dir: str = "/app/cache/swebench"):
        self.cache_dir = Path(cache_dir)
        self.instances_dir = self.cache_dir / "instances"
        self.instances_dir.mkdir(parents=True, exist_ok=True)
        
        self.trigger_file = self.cache_dir / "setup_trigger.json"
        if not self.trigger_file.exists():
            self._create_trigger_file()
    
    def _create_trigger_file(self):
        trigger = [{
            "instance_id": "placeholder",
            "model_patch": "",
            "model_name_or_path": "setup"
        }]
        with open(self.trigger_file, 'w') as f:
            json.dump(trigger, f, indent=2)
        logger.info(f"Created trigger file at {self.trigger_file}")
    
    def is_instance_cached(self, instance_id: str) -> bool:
        marker = self.instances_dir / f"{instance_id}.cached"
        
        if marker.exists():
            logger.info(f"Instance {instance_id} found in cache (marker file)")
            return True
        
        if self._docker_image_exists(instance_id):
            marker.touch()
            logger.info(f"Instance {instance_id} found in cache (Docker image)")
            return True
        
        logger.info(f"Instance {instance_id} not in cache")
        return False
    
    # check if exit in cache
    # download if not
    def _docker_image_exists(self, instance_id: str) -> bool:
        try:
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            for line in result.stdout.strip().split('\n'):
                if instance_id in line and 'sweb.eval' in line:
                    logger.info(f"Found Docker image: {line}")
                    return True
            
            return False
        except Exception as e:
            logger.warning(f"Failed to check Docker image: {e}")
            return False
    
    def download_instance(self, instance_id: str) -> bool:
        logger.info(f"Downloading instance {instance_id} from SWE-bench...")
        
        try:
            with open(self.trigger_file, 'r') as f:
                trigger = json.load(f)
            
            if not isinstance(trigger, list):
                trigger = [trigger]
            
            trigger[0]["instance_id"] = instance_id
            
            with open(self.trigger_file, 'w') as f:
                json.dump(trigger, f, indent=2)
            
            command = [
                "python", "-m", "swebench.harness.run_evaluation",
                "--dataset_name", "princeton-nlp/SWE-bench_Lite",
                "--instance_ids", instance_id,
                "--run_id", "build_check",
                "--max_workers", "1",
                "--predictions_path", str(self.trigger_file)
            ]
            
            logger.info(f"Running: {' '.join(command)}")
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            for line in process.stdout:
                logger.info(f"[SWE-bench] {line.rstrip()}")
            
            process.wait()
            
            if process.returncode == 0:
                marker = self.instances_dir / f"{instance_id}.cached"
                marker.touch()
                logger.info(f"Successfully cached instance {instance_id}")
                return True
            else:
                logger.error(f"Failed to download instance {instance_id} (exit code: {process.returncode})")
                return False
                
        except Exception as e:
            logger.error(f"Error downloading instance {instance_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_cache_info(self) -> Dict[str, any]:
        cached_instances = [marker.stem for marker in self.instances_dir.glob("*.cached")]

        return {
            "cache_dir": str(self.cache_dir),
            "cached_instances": cached_instances,
            "total_cached": len(cached_instances)
        }
    
    def clear_cache(self, instance_id: Optional[str] = None):
        if instance_id:
            marker = self.instances_dir / f"{instance_id}.cached"
            if marker.exists():
                marker.unlink()
                logger.info(f"Cleared cache for {instance_id}")
        else:
            for marker in self.instances_dir.glob("*.cached"):
                marker.unlink()
            logger.info("Cleared all cache")

    def get_docker_image_status(self, instance_id: str) -> Dict[str, any]:
        """Check if Docker image exists for an instance"""
        image_exists = self._docker_image_exists(instance_id)
        image_name = self._get_image_name(instance_id)

        return {
            "instance_id": instance_id,
            "image_exists": image_exists,
            "image_name": image_name,
            "cached": self.is_instance_cached(instance_id)
        }

    def _get_image_name(self, instance_id: str) -> str:
        """Get the expected Docker image name for an instance"""
        # Check if image already exists with exact name
        try:
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                capture_output=True,
                text=True,
                timeout=10
            )

            for line in result.stdout.strip().split('\n'):
                if instance_id in line and 'sweb.eval' in line:
                    return line.strip()
        except Exception:
            pass

        # Return default format
        return f"sweb.eval.x86_64.{instance_id}"

    def build_docker_image(self, instance_id: str) -> Dict[str, any]:
        logger.info(f"Building Docker image for {instance_id}...")

        # Check if already exists
        if self._docker_image_exists(instance_id):
            return {
                "success": True,
                "instance_id": instance_id,
                "message": "Docker image already exists",
                "already_exists": True
            }

        try:
            trigger_data = [{
                "instance_id": instance_id,
                "model_patch": " ",
                "model_name_or_path": "build_check"
            }]

            with open(self.trigger_file, 'w') as f:
                json.dump(trigger_data, f, indent=2)

            command = [
                "python", "-m", "swebench.harness.run_evaluation",
                "--dataset_name", "princeton-nlp/SWE-bench_Lite",
                "--instance_ids", instance_id,
                "--run_id", "build_check",
                "--max_workers", "1",
                "--predictions_path", str(self.trigger_file),
                "--cache_level", "instance"
            ]

            logger.info(f"Running: {' '.join(command)}")

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            output_lines = []
            for line in process.stdout:
                logger.info(f"[swebench] {line.rstrip()}")
                output_lines.append(line.rstrip())

            process.wait()

            image_exists = self._docker_image_exists(instance_id)

            if process.returncode == 0 or image_exists:
                marker = self.instances_dir / f"{instance_id}.cached"
                marker.touch()

                logger.info(f"Successfully built Docker image for {instance_id}")
                return {
                    "success": True,
                    "instance_id": instance_id,
                    "message": "Docker image built successfully",
                    "already_exists": False
                }
            else:
                logger.error(f"Failed to build Docker image for {instance_id}")
                return {
                    "success": False,
                    "instance_id": instance_id,
                    "message": "Docker build failed",
                    "error": "\n".join(output_lines[-20:])
                }

        except Exception as e:
            logger.error(f"Error building Docker image: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "instance_id": instance_id,
                "message": str(e),
                "error": str(e)
            }
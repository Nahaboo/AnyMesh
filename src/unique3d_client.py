import time
import logging
import os
from pathlib import Path
from typing import Dict
import subprocess

logger = logging.getLogger(__name__)

# True when running inside the Unique3D worker container, False on the backend container
IS_WORKER = os.getenv("MESH_GENERATION_PROVIDER") == "unique3d"

def generate_mesh_from_image_unique3d(
    image_path: Path,
    output_path: Path,
    resolution: str = "medium",
    task_id: str = "default"
) -> Dict:
    """
    Main entry point. Acts as an HTTP client on the backend, and as an AI engine on the worker.
    """
    
    if not IS_WORKER:
        import requests
        logger.info(f"[BACKEND] Delegating Unique3D task to remote worker...")
        
        try:
            # En Docker: unique3d-worker:8000, en local: localhost:8001
            worker_url = os.getenv("UNIQUE3D_WORKER_URL", "http://localhost:8001")
            response = requests.post(
                f"{worker_url}/process", 
                json={
                    "image_path": str(image_path),
                    "output_path": str(output_path),
                    "resolution": resolution,
                    "task_id": task_id
                },
                timeout=1800  # 30min: first run loads GPU models
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"[BACKEND] Failed to communicate with worker: {e}")
            return {"success": False, "error": f"AI worker unreachable: {e}"}

    else:
        # Worker logic
        UNIQUE3D_ROOT = "/workspace/Unique3D"
        PYTHON_PATH = "/workspace/miniconda3/envs/unique3d/bin/python"
        
        SITE_PACKAGES = "/workspace/miniconda3/envs/unique3d/lib/python3.10/site-packages"
        # Nvidia library paths installed via pip
        NV_LIBS = [
            f"{SITE_PACKAGES}/torch/lib",
            f"{SITE_PACKAGES}/nvidia/cublas/lib",
            f"{SITE_PACKAGES}/nvidia/cudnn/lib",
            f"{SITE_PACKAGES}/nvidia/cufft/lib",
            f"{SITE_PACKAGES}/nvidia/cuda_runtime/lib",
            f"{SITE_PACKAGES}/nvidia/cuda_cupti/lib",
        ]
        
        try:
            start_time = time.time()
            logger.info(f"[UNIQUE3D] Starting real generation via official scripts")

            # Prepare environment for subprocess
            my_env = os.environ.copy()
            
            # Merge all lib paths into LD_LIBRARY_PATH so ONNX and Torch find their .so files
            current_ld = my_env.get("LD_LIBRARY_PATH", "")
            my_env["LD_LIBRARY_PATH"] = ":".join(NV_LIBS) + (f":{current_ld}" if current_ld else "")
            
            current_pp = my_env.get("PYTHONPATH", "")
            my_env["PYTHONPATH"] = f"{UNIQUE3D_ROOT}:{os.path.join(UNIQUE3D_ROOT, 'scripts')}:{current_pp}"
        
            my_env["CUDA_MODULE_LOADING"] = "LAZY"
            my_env["ORT_CUDA_FLAGS"] = "1"
            
            # Convert relative paths (from backend) to absolute paths (in worker)
            # image_path arrives as e.g. "data/input_images/session_.../image_000.png"
            def to_workspace_path(p):
                s = str(p).replace("\\", "/").lstrip("/")
                if s.startswith("workspace"):
                    return Path(f"/{s}")
                return Path(f"/workspace/{s}")

            abs_input = to_workspace_path(image_path)
            abs_output = to_workspace_path(output_path)

            temp_work_dir = abs_output.parent / f"work_{task_id}"
            temp_work_dir.mkdir(parents=True, exist_ok=True)

            if not abs_input.exists():
                logger.error(f"[UNIQUE3D] Image not found: {abs_input}")
                return {'success': False, 'error': f"Source file not found: {abs_input}"}

            # Full generation: multiview + reconstruction + GLB export
            logger.info("  -> Running full Unique3D pipeline (multiview + reconstruction)...")
            cmd = [
                PYTHON_PATH,
                "scripts/run_unique3d.py",
                "--input_path", str(abs_input),
                "--output_path", str(abs_output),
                "--seed", "42"
            ]

            logger.info(f"  -> Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, env=my_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=UNIQUE3D_ROOT, text=True, timeout=1800)
            logger.info(f"--- UNIQUE3D OUTPUT ---\n{result.stdout}")

            return {
                'success': True,
                'output_file': str(output_path),
                'generation_time_ms': round((time.time() - start_time) * 1000, 2),
                'method': 'unique3d_official_scripts'
            }

        except subprocess.TimeoutExpired:
            logger.error(f"[UNIQUE3D] Script timed out after 1800s")
            return {'success': False, 'error': "Inference script timed out after 30 minutes"}

        except subprocess.CalledProcessError as e:
            output = e.output or e.stderr or ""
            logger.error(f"[UNIQUE3D] Script failed (exit {e.returncode}):\n{output}")
            return {'success': False, 'error': f"Inference script failed (exit {e.returncode}): {output[-500:] if output else 'no output'}"}

        except Exception as e:
            logger.error(f"[UNIQUE3D] Unexpected error: {e}")
            return {'success': False, 'error': f"Unexpected error: {e}"}
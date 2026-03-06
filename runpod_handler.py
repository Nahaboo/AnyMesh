"""
RunPod Serverless handler for Unique3D.
Receives an image as base64, generates a 3D mesh, returns the GLB as base64.

Deployment:
    docker build -f dockerfile.runpod -t youruser/unique3d-worker:runpod .
    docker push youruser/unique3d-worker:runpod
"""

import runpod
import base64
import subprocess
import os
from pathlib import Path

UNIQUE3D_ROOT = "/workspace/Unique3D"
PYTHON_PATH = "/workspace/miniconda3/envs/unique3d/bin/python"
SITE_PACKAGES = "/workspace/miniconda3/envs/unique3d/lib/python3.10/site-packages"

NV_LIBS = [
    f"{SITE_PACKAGES}/torch/lib",
    f"{SITE_PACKAGES}/nvidia/cublas/lib",
    f"{SITE_PACKAGES}/nvidia/cudnn/lib",
    f"{SITE_PACKAGES}/nvidia/cufft/lib",
    f"{SITE_PACKAGES}/nvidia/cuda_runtime/lib",
    f"{SITE_PACKAGES}/nvidia/cuda_cupti/lib",
]


def handler(job):
    job_input = job["input"]

    if "image_base64" not in job_input:
        return {"success": False, "error": "Missing image_base64 in input"}

    # Decode base64 image to a temp file
    img_data = base64.b64decode(job_input["image_base64"])
    tmp_input = "/tmp/runpod_input.png"
    tmp_output = "/tmp/runpod_output.glb"
    Path(tmp_input).write_bytes(img_data)

    # Set up env (same as unique3d_client.py worker mode)
    my_env = os.environ.copy()
    current_ld = my_env.get("LD_LIBRARY_PATH", "")
    my_env["LD_LIBRARY_PATH"] = ":".join(NV_LIBS) + (f":{current_ld}" if current_ld else "")
    my_env["PYTHONPATH"] = f"{UNIQUE3D_ROOT}:{UNIQUE3D_ROOT}/scripts"
    my_env["CUDA_MODULE_LOADING"] = "LAZY"
    my_env["ORT_CUDA_FLAGS"] = "1"

    seed = str(job_input.get("seed", 42))
    cmd = [
        PYTHON_PATH, "scripts/run_unique3d.py",
        "--input_path", tmp_input,
        "--output_path", tmp_output,
        "--seed", seed,
    ]

    print(f"[RunPod] Executing: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, env=my_env, cwd=UNIQUE3D_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    print(f"[RunPod] Output:\n{result.stdout}")

    if result.returncode != 0:
        return {
            "success": False,
            "error": f"Script failed (exit {result.returncode}): {result.stdout[-1000:]}",
        }

    # Encode GLB as base64
    if Path(tmp_output).exists():
        glb_bytes = Path(tmp_output).read_bytes()
        glb_b64 = base64.b64encode(glb_bytes).decode()
        size_mb = len(glb_bytes) / (1024 * 1024)

        # Cleanup
        Path(tmp_input).unlink(missing_ok=True)
        Path(tmp_output).unlink(missing_ok=True)

        return {"success": True, "glb_base64": glb_b64, "size_mb": round(size_mb, 1)}

    return {"success": False, "error": "Output file not created"}


runpod.serverless.start({"handler": handler})

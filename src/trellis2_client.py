"""
TRELLIS.2 provider client.
Sends image to RunPod TRELLIS.2 endpoint, polls for result, saves GLB.

Requires env vars:
    RUNPOD_TRELLIS2_ENDPOINT_ID
    RUNPOD_API_KEY  (shared with TRELLIS v1)
"""
import os
import io
import base64
import time
import logging
import requests
import trimesh
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 2048  # TRELLIS.2 benefits from larger input images


def _encode_image_b64(image_path: Path, max_size: int = MAX_IMAGE_SIZE) -> str:
    """Encode an image as base64 PNG, resizing if larger than max_size px."""
    img = Image.open(image_path).convert("RGBA")
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        logger.info(f"[TRELLIS2] Resized {image_path.name}: {img.size}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def generate_mesh_from_image_trellis2(
    image_path: Path,
    output_path: Path,
    resolution: str = "medium",
) -> dict:
    endpoint_id = os.getenv("RUNPOD_TRELLIS2_ENDPOINT_ID")
    api_key = os.getenv("RUNPOD_API_KEY")

    if not endpoint_id or not api_key:
        return {
            "success": False,
            "error": "RUNPOD_TRELLIS2_ENDPOINT_ID or RUNPOD_API_KEY missing in .env",
        }

    # Map resolution to TRELLIS.2 params
    # decimation_target = absolute face count (replaces v1's simplify ratio)
    resolution_map = {
        "low":    {"resolution": "512",  "decimation_target": 200_000, "texture_size": 1024},
        "medium": {"resolution": "1024", "decimation_target": 500_000, "texture_size": 2048},
        "high":   {"resolution": "1536", "decimation_target": 1_000_000, "texture_size": 4096},
    }
    params = resolution_map.get(resolution, resolution_map["medium"])

    logger.info(f"[TRELLIS2] Provider called: resolution={resolution}, decimation_target={params['decimation_target']}, endpoint={endpoint_id}")

    image_b64 = _encode_image_b64(Path(image_path))
    logger.info(f"[TRELLIS2] Image encoded: {len(image_b64)} chars")

    headers = {"Authorization": f"Bearer {api_key}"}
    submit_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"

    payload = {
        "input": {
            "image_base64": image_b64,
            "resolution": params["resolution"],
            "decimation_target": params["decimation_target"],
            "texture_size": params["texture_size"],
            "seed": 0,
        },
        "policy": {"executionTimeout": 900000},  # 15 min
    }

    t0 = time.time()
    logger.info(f"[TRELLIS2] Submitting job to {submit_url}...")
    resp = requests.post(submit_url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    job_id = resp.json()["id"]
    logger.info(f"[TRELLIS2] Job submitted: {job_id} (took {time.time()-t0:.1f}s)")

    # Poll for result
    status_url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
    timeout_s = 900  # 15 min (TRELLIS.2 is slower than v1)

    while time.time() - t0 < timeout_s:
        time.sleep(5)
        try:
            resp = requests.get(status_url, headers=headers, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[TRELLIS2] Poll request failed: {e}, retrying...")
            continue

        data = resp.json()
        status = data.get("status")
        logger.info(f"[TRELLIS2] Job {job_id}: {status}")

        if status == "COMPLETED":
            output = data["output"]
            if not output.get("success"):
                return {
                    "success": False,
                    "error": output.get("error", "Unknown error from worker"),
                }

            # Decode and save GLB
            glb_bytes = base64.b64decode(output["glb_base64"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(glb_bytes)

            # Get mesh stats
            mesh = trimesh.load(str(output_path), force="mesh")

            return {
                "success": True,
                "output_file": str(output_path),
                "output_filename": output_path.name,
                "vertices_count": len(mesh.vertices),
                "faces_count": len(mesh.faces),
                "resolution": resolution,
                "generation_time_ms": round((time.time() - t0) * 1000),
                "method": "trellis2_runpod",
                "api_credits_used": 0,
            }

        elif status == "FAILED":
            error = data.get("output", {}).get("error", data.get("error", "Job failed"))
            return {"success": False, "error": f"RunPod FAILED: {error}"}

    return {"success": False, "error": f"Timeout after {timeout_s}s"}

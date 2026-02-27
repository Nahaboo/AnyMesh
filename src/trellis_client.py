"""
TRELLIS provider client.
Sends image(s) to RunPod TRELLIS endpoint, polls for result, saves GLB.
Supports single-image and multi-image (run_multi_image) modes.
"""
import os
import io
import base64
import time
import logging
import requests
from pathlib import Path
from typing import List
from PIL import Image

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 1024  # TRELLIS reduit a 518px en interne, 1024 suffit


def _encode_image_b64(image_path: Path, max_size: int = MAX_IMAGE_SIZE) -> str:
    """Encode une image en base64, redimensionnee si > max_size px."""
    img = Image.open(image_path)
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        logger.info(f"[TRELLIS] Resized {image_path.name}: {img.size}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def generate_mesh_from_image_trellis(
    image_path: Path,
    output_path: Path,
    resolution: str = "medium",
    extra_images: List[Path] = None,
) -> dict:
    endpoint_id = os.getenv("RUNPOD_TRELLIS_ENDPOINT_ID")
    api_key = os.getenv("RUNPOD_API_KEY")

    if not endpoint_id or not api_key:
        return {
            "success": False,
            "error": "RUNPOD_TRELLIS_ENDPOINT_ID ou RUNPOD_API_KEY manquant dans .env",
        }

    # Map resolution to TRELLIS texture_size + simplify ratio
    # simplify = ratio of faces to REMOVE (0.60 = keep 40%, best quality/clean tradeoff)
    resolution_map = {
        "low": {"texture_size": 512, "simplify": 0.80},
        "medium": {"texture_size": 1024, "simplify": 0.60},
        "high": {"texture_size": 2048, "simplify": 0.30},
    }
    params = resolution_map.get(resolution, resolution_map["medium"])

    # Collect all image paths
    all_images = [Path(image_path)]
    if extra_images:
        all_images.extend(Path(p) for p in extra_images)

    logger.info(f"[TRELLIS] Provider called: {len(all_images)} image(s), resolution={resolution}, endpoint={endpoint_id}")

    # Build payload (single or multi)
    headers = {"Authorization": f"Bearer {api_key}"}
    submit_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"

    if len(all_images) > 1:
        images_b64 = [_encode_image_b64(p) for p in all_images]
        logger.info(f"[TRELLIS] Multi-image: {len(images_b64)} images encoded")
        input_data = {
            "images_base64": images_b64,
            "texture_size": params["texture_size"],
            "simplify": params["simplify"],
        }
    else:
        image_b64 = _encode_image_b64(all_images[0])
        logger.info(f"[TRELLIS] Single image encoded: {len(image_b64)} chars")
        input_data = {
            "image_base64": image_b64,
            "texture_size": params["texture_size"],
            "simplify": params["simplify"],
        }

    payload = {
        "input": input_data,
        "policy": {"executionTimeout": 600000},  # 10 min
    }

    t0 = time.time()
    logger.info(f"[TRELLIS] Submitting job to {submit_url}...")
    resp = requests.post(submit_url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    job_id = resp.json()["id"]
    logger.info(f"[TRELLIS] Job submitted: {job_id} (took {time.time()-t0:.1f}s)")

    # Poll for result
    status_url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
    timeout_s = 600  # 10 min

    while time.time() - t0 < timeout_s:
        time.sleep(5)
        resp = requests.get(status_url, headers=headers, timeout=30)
        data = resp.json()
        status = data.get("status")
        logger.info(f"[TRELLIS] Job {job_id}: {status}")

        if status == "COMPLETED":
            output = data["output"]
            if not output.get("success"):
                return {
                    "success": False,
                    "error": output.get("error", "Unknown error"),
                }

            # Decode and save GLB
            glb_bytes = base64.b64decode(output["glb_base64"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(glb_bytes)

            # Get mesh stats
            import trimesh

            mesh = trimesh.load(str(output_path), force="mesh")

            return {
                "success": True,
                "output_file": str(output_path),
                "output_filename": output_path.name,
                "vertices_count": len(mesh.vertices),
                "faces_count": len(mesh.faces),
                "resolution": resolution,
                "generation_time_ms": round((time.time() - t0) * 1000),
                "method": "trellis_runpod",
                "api_credits_used": 0,
            }

        elif status == "FAILED":
            error = data.get("output", {}).get(
                "error", data.get("error", "Job failed")
            )
            return {"success": False, "error": f"RunPod FAILED: {error}"}

    return {"success": False, "error": f"Timeout apres {timeout_s}s"}

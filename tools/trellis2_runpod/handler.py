"""
RunPod Serverless handler for TRELLIS.2.
Receives an image as base64, generates a 3D mesh, uploads GLB to backend.

BiRefNet (background removal) is disabled: images are preprocessed manually
(resize to 1024x1024, RGBA) and passed with preprocess_image=False.
This avoids the meta tensor crash caused by briaai/RMBG-2.0 loading.

Input:
    image_base64:                str  (required)
    job_id:                      str  (required, used as filename)
    resolution:                  str  "512" | "1024" | "1536" (default: "1024")
    decimation_target:           int  target face count (default: 500000)
    texture_size:                int  1024 | 2048 | 4096 (default: 2048)
    seed:                        int  (default: 0)
    ss_guidance_strength:        float (default: 7.5)
    ss_sampling_steps:           int   (default: 12)
    shape_slat_guidance_strength: float (default: 3.0)
    shape_slat_sampling_steps:   int   (default: 12)
    tex_slat_guidance_strength:  float (default: 3.0)
    tex_slat_sampling_steps:     int   (default: 12)

Output:
    { "success": true, "glb_url": "http://...", "size_mb": 12.3 }
    { "success": false, "error": "..." }

Env vars:
    BACKEND_UPLOAD_URL  URL to POST the GLB (e.g. http://VPS_IP/upload-glb-result)

Deployment:
    docker build -f tools/trellis2_runpod/Dockerfile -t youruser/trellis2-worker:latest .
    docker push youruser/trellis2-worker:latest
    RunPod: create serverless endpoint with this image, GPU >= A5000 (24 GB)
"""

import os
import runpod

print(f"[TRELLIS2] HF_HOME={os.environ.get('HF_HOME', 'NOT SET')}")
import base64
import io
import traceback
import requests
import numpy as np
from collections import deque
from pathlib import Path
from PIL import Image

# Try to load rembg — fallback to flood-fill if unavailable
try:
    from rembg import remove as _rembg_remove
    _REMBG_AVAILABLE = True
    print("[TRELLIS2] rembg loaded successfully.")
except Exception as e:
    _REMBG_AVAILABLE = False
    print(f"[TRELLIS2] rembg not available, falling back to flood-fill: {e}")


# Patch: skip BiRefNet load entirely.
# from_pretrained calls BiRefNet(**args) which immediately runs
# AutoModelForImageSegmentation.from_pretrained with trust_remote_code=True,
# loading briaai/RMBG-2.0. That model's birefnet.py calls .item() in __init__
# on meta tensors (low_cpu_mem_usage=True default) → NotImplementedError crash.
# Fix: replace BiRefNet.__init__ with a no-op before from_pretrained runs.
# At runtime we use preprocess_image=False so rembg_model is never called.
print("[TRELLIS2] Patching BiRefNet to skip load...")
try:
    from trellis2.pipelines import rembg as _rembg

    def _noop_birefnet_init(self, model_name="ZhengPeng7/BiRefNet"):
        self.model = None
        print("[TRELLIS2] BiRefNet skipped (no-op patch active)")

    _rembg.BiRefNet.__init__ = _noop_birefnet_init
    print("[TRELLIS2] BiRefNet patch applied.")
except Exception as e:
    print(f"[TRELLIS2] WARNING: BiRefNet patch failed: {e}")
    traceback.print_exc()


# Load pipeline at cold start (outside handler to reuse across jobs)
print("[TRELLIS2] Loading pipeline...")
try:
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    from o_voxel import postprocess as o_voxel_postprocess

    pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
    pipeline.cuda()
    print("[TRELLIS2] Pipeline loaded successfully.")
except Exception as e:
    print(f"[TRELLIS2] FATAL: Failed to load pipeline: {e}")
    traceback.print_exc()
    pipeline = None


def _remove_background_floodfill(image: Image.Image, threshold: int = 240) -> Image.Image:
    """
    Flood-fill from image edges to remove uniform background.
    Only pixels connected to the border and brighter than threshold are made transparent.
    Preserves bright areas inside the object.
    """
    rgba = image.convert("RGBA")
    data = np.array(rgba)
    h, w = data.shape[:2]
    visited = np.zeros((h, w), dtype=bool)
    mask = np.zeros((h, w), dtype=bool)

    queue = deque()
    for x in range(w):
        for y in [0, h - 1]:
            r, g, b = data[y, x, :3]
            if r >= threshold and g >= threshold and b >= threshold and not visited[y, x]:
                queue.append((y, x))
                visited[y, x] = True
    for y in range(h):
        for x in [0, w - 1]:
            r, g, b = data[y, x, :3]
            if r >= threshold and g >= threshold and b >= threshold and not visited[y, x]:
                queue.append((y, x))
                visited[y, x] = True

    while queue:
        y, x = queue.popleft()
        mask[y, x] = True
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                r, g, b = data[ny, nx, :3]
                if r >= threshold and g >= threshold and b >= threshold:
                    visited[ny, nx] = True
                    queue.append((ny, nx))

    data[mask, 3] = 0
    removed = int(mask.sum())
    print(f"[TRELLIS2] Flood-fill removed: {removed} pixels made transparent")
    return Image.fromarray(data)


def remove_background(image: Image.Image) -> Image.Image:
    """
    Remove background using rembg (U2Net) if available, else fall back to flood-fill.
    """
    if _REMBG_AVAILABLE:
        try:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            result = _rembg_remove(buf.getvalue())
            out = Image.open(io.BytesIO(result)).convert("RGBA")
            print("[TRELLIS2] rembg background removal done.")
            return out
        except Exception as e:
            print(f"[TRELLIS2] rembg failed, falling back to flood-fill: {e}")
    return _remove_background_floodfill(image)


def preprocess_image(image: Image.Image, size: int = 1024) -> Image.Image:
    """
    Remove background, resize to size x size (LANCZOS), pad to square.
    Replaces the pipeline's preprocess_image step (which requires BiRefNet).
    """
    image = remove_background(image)
    image.thumbnail((size, size), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - image.width) // 2, (size - image.height) // 2)
    result.paste(image, offset)
    return result


def handler(job):
    if pipeline is None:
        return {"success": False, "error": "Pipeline not loaded (cold start failure)"}

    job_input = job["input"]

    if "image_base64" not in job_input:
        return {"success": False, "error": "Missing image_base64 in input"}

    # Decode and preprocess image manually (BiRefNet disabled)
    try:
        img_bytes = base64.b64decode(job_input["image_base64"])
        image = Image.open(io.BytesIO(img_bytes))
        image = preprocess_image(image, size=1024)
        print(f"[TRELLIS2] Image preprocessed: {image.size}, mode={image.mode}")
    except Exception as e:
        return {"success": False, "error": f"Failed to decode/preprocess image: {e}"}

    # Parse params
    pipeline_type = {
        "512": "512",
        "1024": "1024_cascade",
        "1536": "1536_cascade",
    }.get(str(job_input.get("pipeline_type", "1024")), "1024_cascade")
    decimation_target = int(job_input.get("decimation_target", 500000))
    texture_size = int(job_input.get("texture_size", 2048))
    seed = int(job_input.get("seed", 0))
    ss_guidance_strength = float(job_input.get("ss_guidance_strength", 7.5))
    ss_sampling_steps = int(job_input.get("ss_sampling_steps", 12))
    shape_slat_guidance_strength = float(job_input.get("shape_slat_guidance_strength", 3.0))
    shape_slat_sampling_steps = int(job_input.get("shape_slat_sampling_steps", 12))
    tex_slat_guidance_strength = float(job_input.get("tex_slat_guidance_strength", 3.0))
    tex_slat_sampling_steps = int(job_input.get("tex_slat_sampling_steps", 12))

    print(f"[TRELLIS2] Generating: pipeline_type={pipeline_type}, decimation_target={decimation_target}, texture_size={texture_size}")

    try:
        # preprocess_image=False: image already preprocessed manually above
        outputs = pipeline.run(
            image,
            seed=seed,
            pipeline_type=pipeline_type,
            preprocess_image=False,
            sparse_structure_sampler_params={
                "steps": ss_sampling_steps,
                "guidance_strength": ss_guidance_strength,
                "guidance_rescale": 0.7,
                "rescale_t": 5.0,
            },
            shape_slat_sampler_params={
                "steps": shape_slat_sampling_steps,
                "guidance_strength": shape_slat_guidance_strength,
                "guidance_rescale": 0.5,
                "rescale_t": 3.0,
            },
            tex_slat_sampler_params={
                "steps": tex_slat_sampling_steps,
                "guidance_strength": tex_slat_guidance_strength,
                "guidance_rescale": 0.0,
                "rescale_t": 3.0,
            },
        )
        mesh = outputs[0]

        # Hard polygon cap before export
        mesh.simplify(16_777_216)

        print(f"[TRELLIS2] Mesh generated. Running to_glb (decimation_target={decimation_target})...")

        # Export GLB
        glb = o_voxel_postprocess.to_glb(
            vertices=mesh.vertices,
            faces=mesh.faces,
            attr_volume=mesh.attrs,
            coords=mesh.coords,
            attr_layout=mesh.layout,
            voxel_size=mesh.voxel_size,
            aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
            decimation_target=decimation_target,
            texture_size=texture_size,
            remesh=True,
            remesh_band=1,
            remesh_project=0,
            verbose=False,
        )

        # Serialize GLB to bytes
        tmp_path = Path("/tmp/trellis2_output.glb")
        glb.export(str(tmp_path), extension_webp=True)
        glb_bytes = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)

        size_mb = round(len(glb_bytes) / (1024 * 1024), 1)
        print(f"[TRELLIS2] Done. GLB size: {size_mb} MB")

        # Upload GLB to backend
        upload_url = os.environ.get("BACKEND_UPLOAD_URL")
        print(f"[TRELLIS2] BACKEND_UPLOAD_URL={upload_url}")
        if not upload_url:
            return {"success": False, "error": "BACKEND_UPLOAD_URL not set"}

        job_id = job.get("id", "unknown")
        resp = requests.post(
            upload_url,
            files={"file": ("result.glb", glb_bytes, "model/gltf-binary")},
            data={"job_id": job_id},
            timeout=60,
        )
        print(f"[TRELLIS2] Upload response: {resp.status_code} {resp.text[:200]}")
        resp.raise_for_status()
        glb_url = resp.json()["url"]
        print(f"[TRELLIS2] GLB uploaded: {glb_url}")

        return {"success": True, "glb_url": glb_url, "size_mb": size_mb}

    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": f"Generation failed: {e}"}


runpod.serverless.start({"handler": handler})

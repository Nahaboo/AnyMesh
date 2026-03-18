"""
RunPod Serverless handler for TRELLIS.2.
Receives an image as base64, generates a 3D mesh, returns the GLB as base64.

BiRefNet (background removal) is disabled: images are preprocessed manually
(resize to 1024x1024, RGBA) and passed with preprocess_image=False.
This avoids the meta tensor crash caused by briaai/RMBG-2.0 loading.

Input:
    image_base64:                str  (required)
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
    { "success": true, "glb_base64": "...", "size_mb": 12.3 }
    { "success": false, "error": "..." }

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
from pathlib import Path
from PIL import Image


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


def preprocess_image(image: Image.Image, size: int = 1024) -> Image.Image:
    """
    Resize image to size x size (LANCZOS), convert to RGBA.
    Replaces the pipeline's preprocess_image step (which requires BiRefNet).
    Keeps aspect ratio by padding with transparency.
    """
    image = image.convert("RGBA")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)

    # Pad to exact square with transparent background
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

        glb_b64 = base64.b64encode(glb_bytes).decode()
        size_mb = round(len(glb_bytes) / (1024 * 1024), 1)
        print(f"[TRELLIS2] Done. GLB size: {size_mb} MB")

        return {"success": True, "glb_base64": glb_b64, "size_mb": size_mb}

    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": f"Generation failed: {e}"}


runpod.serverless.start({"handler": handler})

"""
RunPod Serverless handler for TRELLIS.2.
Receives an image as base64, generates a 3D mesh, returns the GLB as base64.

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
import base64
import io
import traceback
from pathlib import Path
from PIL import Image
from huggingface_hub import login

# Authenticate with HuggingFace if token is provided
hf_token = os.environ.get("HF_TOKEN")
if hf_token:
    login(token=hf_token)
    print("[TRELLIS2] HuggingFace login successful.")
else:
    print("[TRELLIS2] Warning: HF_TOKEN not set.")

# Pre-download RMBG-2.0 custom code and patch device_map="auto" -> device_map=None
# birefnet.py is a custom_code model — transformers downloads it at runtime and executes it.
# device_map="auto" causes Tensor.item() to fail on meta tensors during __init__.
import subprocess
subprocess.run([
    "python", "-c",
    "from huggingface_hub import snapshot_download; snapshot_download('briaai/RMBG-2.0')"
], check=False)
import glob
for f in glob.glob("/workspace/models/modules/transformers_modules/briaai/**/*.py", recursive=True):
    with open(f, "r") as fh:
        content = fh.read()
    if 'device_map="auto"' in content:
        with open(f, "w") as fh:
            fh.write(content.replace('device_map="auto"', 'device_map=None'))
        print(f"[TRELLIS2] Patched device_map in {f}")

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


def handler(job):
    if pipeline is None:
        return {"success": False, "error": "Pipeline not loaded (cold start failure)"}

    job_input = job["input"]

    if "image_base64" not in job_input:
        return {"success": False, "error": "Missing image_base64 in input"}

    # Decode image
    try:
        img_bytes = base64.b64decode(job_input["image_base64"])
        image = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    except Exception as e:
        return {"success": False, "error": f"Failed to decode image: {e}"}

    # Parse params
    resolution = str(job_input.get("resolution", "1024"))
    decimation_target = int(job_input.get("decimation_target", 500000))
    texture_size = int(job_input.get("texture_size", 2048))
    seed = int(job_input.get("seed", 0))
    ss_guidance_strength = float(job_input.get("ss_guidance_strength", 7.5))
    ss_sampling_steps = int(job_input.get("ss_sampling_steps", 12))
    shape_slat_guidance_strength = float(job_input.get("shape_slat_guidance_strength", 3.0))
    shape_slat_sampling_steps = int(job_input.get("shape_slat_sampling_steps", 12))
    tex_slat_guidance_strength = float(job_input.get("tex_slat_guidance_strength", 3.0))
    tex_slat_sampling_steps = int(job_input.get("tex_slat_sampling_steps", 12))

    print(f"[TRELLIS2] Generating: resolution={resolution}, decimation_target={decimation_target}, texture_size={texture_size}")

    try:
        # Run pipeline
        outputs = pipeline.run(
            image,
            seed=seed,
            resolution=resolution,
            ss_guidance_strength=ss_guidance_strength,
            ss_guidance_rescale=0.0,
            ss_sampling_steps=ss_sampling_steps,
            ss_rescale_t=0.7,
            shape_slat_guidance_strength=shape_slat_guidance_strength,
            shape_slat_guidance_rescale=0.0,
            shape_slat_sampling_steps=shape_slat_sampling_steps,
            shape_slat_rescale_t=0.7,
            tex_slat_guidance_strength=tex_slat_guidance_strength,
            tex_slat_guidance_rescale=0.0,
            tex_slat_sampling_steps=tex_slat_sampling_steps,
            tex_slat_rescale_t=0.7,
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

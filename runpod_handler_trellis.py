"""
RunPod serverless handler for TRELLIS image-to-3D generation.
Receives image as base64, runs TRELLIS inference, returns GLB as base64.
"""
import runpod
import base64
import os
import time
import torch
from pathlib import Path
from PIL import Image

os.environ['SPCONV_ALGO'] = 'native'

# Load pipeline once at startup (warm start for subsequent requests)
print("[TRELLIS] Loading pipeline...")
from trellis.pipelines import TrellisImageTo3DPipeline
from trellis.utils import postprocessing_utils

pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
pipeline.cuda()
print("[TRELLIS] Pipeline ready.")


def handler(job):
    try:
        input_data = job["input"]
        seed = input_data.get("seed", 42)
        simplify = input_data.get("simplify", 0.95)
        texture_size = input_data.get("texture_size", 1024)

        # Decode images (single or multi)
        # Single: "image_base64": "..."
        # Multi:  "images_base64": ["...", "...", ...]
        tmp_files = []
        images = []

        if "images_base64" in input_data:
            # Multi-image mode
            for i, img_b64 in enumerate(input_data["images_base64"]):
                img_bytes = base64.b64decode(img_b64)
                tmp_path = Path(f"/tmp/trellis_input_{i}.png")
                tmp_path.write_bytes(img_bytes)
                images.append(Image.open(tmp_path))
                tmp_files.append(tmp_path)
            print(f"[TRELLIS] Multi-image mode: {len(images)} images")
        else:
            # Single image mode
            img_bytes = base64.b64decode(input_data["image_base64"])
            tmp_path = Path("/tmp/trellis_input.png")
            tmp_path.write_bytes(img_bytes)
            images.append(Image.open(tmp_path))
            tmp_files.append(tmp_path)

        # Sampling params (recommended by TRELLIS repo)
        ss_params = input_data.get("sparse_structure_sampler_params", {
            "steps": 12,
            "cfg_strength": 7.5,
        })
        slat_params = input_data.get("slat_sampler_params", {
            "steps": 12,
            "cfg_strength": 3,
        })

        # Inference
        t0 = time.time()
        if len(images) > 1:
            mode = input_data.get("mode", "stochastic")
            outputs = pipeline.run_multi_image(
                images,
                seed=seed,
                sparse_structure_sampler_params=ss_params,
                slat_sampler_params=slat_params,
                mode=mode,
                formats=['mesh', 'gaussian'],
            )
        else:
            outputs = pipeline.run(
                images[0],
                seed=seed,
                sparse_structure_sampler_params=ss_params,
                slat_sampler_params=slat_params,
                formats=['mesh', 'gaussian'],
            )
        t_inference = time.time() - t0
        print(f"[TRELLIS] Inference done in {t_inference:.1f}s ({len(images)} image(s))")

        # Export to GLB (textured mesh)
        fill_holes = input_data.get("fill_holes", True)
        fill_holes_max_size = input_data.get("fill_holes_max_size", 0.15)

        t1 = time.time()
        glb = postprocessing_utils.to_glb(
            outputs['gaussian'][0],
            outputs['mesh'][0],
            simplify=simplify,
            texture_size=texture_size,
            fill_holes=fill_holes,
            fill_holes_max_size=fill_holes_max_size,
        )
        tmp_output = Path("/tmp/trellis_output.glb")
        glb.export(str(tmp_output))
        t_export = time.time() - t1
        print(f"[TRELLIS] GLB export done in {t_export:.1f}s")

        # Encode result as base64
        glb_b64 = base64.b64encode(tmp_output.read_bytes()).decode()
        size_mb = tmp_output.stat().st_size / (1024 * 1024)

        # Cleanup VRAM (critical for subsequent requests)
        torch.cuda.empty_cache()

        # Cleanup temp files
        for f in tmp_files:
            f.unlink(missing_ok=True)
        tmp_output.unlink(missing_ok=True)

        return {
            "success": True,
            "glb_base64": glb_b64,
            "size_mb": round(size_mb, 1),
            "inference_time_s": round(t_inference, 1),
            "export_time_s": round(t_export, 1),
            "images_count": len(images),
        }

    except Exception as e:
        torch.cuda.empty_cache()
        return {"success": False, "error": str(e)}


runpod.serverless.start({"handler": handler})

"""
Local TripoSR client for 3D mesh generation.
Open-source model co-developed by Tripo AI and Stability AI. Generates meshes from a single image in < 0.5s on GPU.
"""

import sys
import time
import trimesh
from pathlib import Path
from typing import Dict

# Add TripoSR to Python path
TRIPOSR_PATH = Path(__file__).parent.parent / "tools" / "TripoSR"
if str(TRIPOSR_PATH) not in sys.path:
    sys.path.insert(0, str(TRIPOSR_PATH))

# Global model cache to avoid reloading on every call
_model_cache = None
_model_device = None


def _get_model(device: str):
    """Load the TripoSR model, cached after the first call."""
    global _model_cache, _model_device

    if _model_cache is not None and _model_device == device:
        return _model_cache

    from tsr.system import TSR

    print(f"  [TRIPOSR] Loading model (first time, will be cached)...")
    model = TSR.from_pretrained(
        "stabilityai/TripoSR",
        config_name="config.yaml",
        weight_name="model.ckpt"
    )
    model.to(device)
    model.renderer.set_chunk_size(8192)

    _model_cache = model
    _model_device = device

    return model


def generate_mesh_from_image_triposr(
    image_path: Path,
    output_path: Path,
    resolution: str = "medium",
    foreground_ratio: float = 0.85
) -> Dict:
    """
    Generate a 3D mesh from an image using local TripoSR. Free, no API key required.

    resolution controls marching cubes resolution: low=128, medium=256, high=512.
    """
    start_time = time.time()

    # Resolution to marching cubes resolution mapping
    MC_RESOLUTION = {
        'low': 128,
        'medium': 256,
        'high': 512
    }
    mc_res = MC_RESOLUTION.get(resolution, 256)

    try:
        # Lazy imports to avoid loading at server startup
        from tsr.utils import remove_background, resize_foreground
        from PIL import Image
        import torch
        import numpy as np

        print(f"\n[TRIPOSR] Generating mesh from image")
        print(f"  Input: {image_path.name}")
        print(f"  Resolution: {resolution} (mc={mc_res})")

        # Detect device
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"  Device: {device}")

        if device == "cpu":
            print("  [WARN] Running on CPU - this will be slow!")

        # Load model (cached)
        model = _get_model(device)

        # Image preprocessing (matches the official run.py pipeline)
        print(f"  Preprocessing image...")
        image = remove_background(Image.open(image_path), force=True)
        image = resize_foreground(image, foreground_ratio)
        # 50% grey background via alpha compositing (matches official pipeline)
        image = np.array(image).astype(np.float32) / 255.0
        image = image[:, :, :3] * image[:, :, 3:4] + (1 - image[:, :, 3:4]) * 0.5
        image = Image.fromarray((image * 255.0).astype(np.uint8))

        # Generate 3D representation
        print(f"  Generating 3D representation...")
        with torch.no_grad():
            scene_codes = model([image], device=device)

        # Extract mesh
        print(f"  Extracting mesh (resolution={mc_res})...")
        meshes = model.extract_mesh(
            scene_codes,
            has_vertex_color=True,
            resolution=mc_res,
            threshold=25.0
        )
        mesh = meshes[0]

        # GLB-First: force .glb extension
        if output_path.suffix.lower() != '.glb':
            output_path = output_path.with_suffix('.glb')

        print(f"  Exporting to GLB: {output_path.name}")
        mesh.export(str(output_path), file_type='glb')

        # Reload for stats
        final_mesh = trimesh.load(str(output_path))
        if hasattr(final_mesh, 'geometry'):
            meshes_list = list(final_mesh.geometry.values())
            if len(meshes_list) > 0:
                final_mesh = meshes_list[0] if len(meshes_list) == 1 else trimesh.util.concatenate(meshes_list)

        vertices_count = len(final_mesh.vertices)
        faces_count = len(final_mesh.faces)
        generation_time = (time.time() - start_time) * 1000

        print(f"  [OK] Mesh generated successfully")
        print(f"    Vertices: {vertices_count}")
        print(f"    Faces: {faces_count}")
        print(f"    Time: {generation_time:.2f}ms")

        return {
            'success': True,
            'output_file': str(output_path),
            'output_filename': output_path.name,
            'vertices_count': vertices_count,
            'faces_count': faces_count,
            'resolution': resolution,
            'generation_time_ms': round(generation_time, 2),
            'method': 'triposr_local',
            'api_credits_used': 0  # Free
        }

    except ImportError as e:
        error_msg = str(e)
        if 'tsr' in error_msg.lower():
            return {
                'success': False,
                'error': f"TripoSR not installed. Run: pip install -r tools/TripoSR/requirements.txt"
            }
        return {
            'success': False,
            'error': f"Missing dependency: {error_msg}"
        }

    except torch.cuda.OutOfMemoryError:
        return {
            'success': False,
            'error': "Insufficient GPU memory. Try a lower resolution or free some VRAM."
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f"TripoSR error: {str(e)}",
            'error_type': type(e).__name__
        }

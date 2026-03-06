"""
Texture baking: transfers texture from high-poly to low-poly via KDTree.

Pipeline: load high-poly GLB -> LSCM unwrap low-poly -> KDTree nearest vertex
-> sample colors -> rasterize baked texture by barycentric interpolation.
"""

import numpy as np
import trimesh
from pathlib import Path
from typing import Dict, Any
from PIL import Image
from scipy.spatial import cKDTree


def _sample_texture(tex_arr: np.ndarray, uv: np.ndarray) -> np.ndarray:
    """Sample colors from a texture array (H, W, C) at UV coordinates (N, 2) in [0, 1]. Returns (N, C)."""
    H, W = tex_arr.shape[:2]
    px = (uv[:, 0] * W).astype(int) % W
    py = ((1.0 - uv[:, 1]) * H).astype(int) % H
    return tex_arr[py, px]


def _rasterize_triangle(
    baked: np.ndarray,
    uv0: np.ndarray, uv1: np.ndarray, uv2: np.ndarray,
    c0: np.ndarray, c1: np.ndarray, c2: np.ndarray,
    texture_size: int
):
    """
    Rasterize a triangle into the baked texture via barycentric interpolation.
    uv*: (2,) in [0, 1]. c*: (3,) RGB uint8.
    """
    # Convert UVs to pixel coordinates
    p0 = np.array([uv0[0] * texture_size, (1.0 - uv0[1]) * texture_size])
    p1 = np.array([uv1[0] * texture_size, (1.0 - uv1[1]) * texture_size])
    p2 = np.array([uv2[0] * texture_size, (1.0 - uv2[1]) * texture_size])

    # Triangle bounding box in pixels
    min_x = max(0, int(min(p0[0], p1[0], p2[0])))
    max_x = min(texture_size - 1, int(max(p0[0], p1[0], p2[0])) + 1)
    min_y = max(0, int(min(p0[1], p1[1], p2[1])))
    max_y = min(texture_size - 1, int(max(p0[1], p1[1], p2[1])) + 1)

    if min_x >= max_x or min_y >= max_y:
        return

    # Barycentric denominator
    denom = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
    if abs(denom) < 1e-8:
        return

    # Pixel grid over bounding box
    xs = np.arange(min_x, max_x + 1)
    ys = np.arange(min_y, max_y + 1)
    gx, gy = np.meshgrid(xs + 0.5, ys + 0.5)
    gx = gx.ravel()
    gy = gy.ravel()

    # Barycentric coordinates
    w0 = ((p1[1] - p2[1]) * (gx - p2[0]) + (p2[0] - p1[0]) * (gy - p2[1])) / denom
    w1 = ((p2[1] - p0[1]) * (gx - p2[0]) + (p0[0] - p2[0]) * (gy - p2[1])) / denom
    w2 = 1.0 - w0 - w1

    # Keep only pixels inside the triangle
    mask = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
    if not np.any(mask):
        return

    gx_m = gx[mask].astype(int)
    gy_m = gy[mask].astype(int)
    w0_m = w0[mask, np.newaxis]
    w1_m = w1[mask, np.newaxis]
    w2_m = w2[mask, np.newaxis]

    # Interpolate color
    colors = (w0_m * c0 + w1_m * c1 + w2_m * c2).clip(0, 255).astype(np.uint8)
    baked[gy_m, gx_m] = colors


def bake_texture(
    high_poly_glb: Path,
    low_poly_mesh: trimesh.Trimesh,
    output_texture_path: Path,
    texture_size: int = 1024
) -> Dict[str, Any]:
    """
    Bake texture from the high-poly GLB onto the retopologized low-poly mesh.

    Returns a dict with keys: success, textured_mesh, texture_filename, error.
    """
    try:
        # 1. Load high poly and extract texture + UVs
        loaded = trimesh.load(str(high_poly_glb), force='scene')
        if hasattr(loaded, 'geometry'):
            high_mesh = list(loaded.geometry.values())[0]
        else:
            high_mesh = loaded

        if not hasattr(high_mesh.visual, 'uv') or high_mesh.visual.uv is None:
            return {"success": False, "error": "High poly has no UV coordinates"}

        if not hasattr(high_mesh.visual, 'material') or \
           not hasattr(high_mesh.visual.material, 'baseColorTexture') or \
           high_mesh.visual.material.baseColorTexture is None:
            return {"success": False, "error": "High poly has no baseColorTexture"}

        high_uv = np.array(high_mesh.visual.uv)          # (N, 2)
        high_tex = high_mesh.visual.material.baseColorTexture
        tex_arr = np.array(high_tex.convert('RGB'))       # (H, W, 3)

        print(f"[BAKING] High poly: {len(high_mesh.vertices)}v, texture {tex_arr.shape[1]}x{tex_arr.shape[0]}")

        # 2. LSCM unwrap of low poly
        print(f"[BAKING] Unwrapping low poly ({len(low_poly_mesh.vertices)}v)...")
        low_unwrapped = low_poly_mesh.unwrap()

        if not hasattr(low_unwrapped.visual, 'uv') or low_unwrapped.visual.uv is None:
            return {"success": False, "error": "LSCM unwrap failed: no UVs produced"}

        low_uv = np.array(low_unwrapped.visual.uv)       # (M, 2)

        # 3. KDTree: find nearest high-poly vertex for each low-poly vertex
        print(f"[BAKING] Building KDTree on {len(high_mesh.vertices)} vertices...")
        tree = cKDTree(high_mesh.vertices)
        _, indices = tree.query(low_poly_mesh.vertices)   # indices shape (M,)

        # 4. Sample high-poly vertex colors via their UVs
        high_uv_for_low = high_uv[indices]                # (M, 2) corresponding high-poly UVs
        vertex_colors = _sample_texture(tex_arr, high_uv_for_low).astype(np.float32)  # (M, 3)

        # 5. Rasterize baked texture triangle by triangle
        print(f"[BAKING] Rasterizing {len(low_unwrapped.faces)} triangles into {texture_size}x{texture_size} texture...")
        baked = np.zeros((texture_size, texture_size, 3), dtype=np.uint8)

        for face in low_unwrapped.faces:
            v0, v1, v2 = face
            _rasterize_triangle(
                baked,
                low_uv[v0], low_uv[v1], low_uv[v2],
                vertex_colors[v0], vertex_colors[v1], vertex_colors[v2],
                texture_size
            )

        # 6. Save baked texture as PNG
        baked_img = Image.fromarray(baked)
        baked_img.save(str(output_texture_path))
        print(f"[BAKING] Texture saved: {output_texture_path.name}")

        # 7. Assign baked texture to low poly
        material = trimesh.visual.material.PBRMaterial(
            baseColorTexture=baked_img,
            name='baked_diffuse'
        )
        low_unwrapped.visual = trimesh.visual.TextureVisuals(
            uv=low_uv,
            material=material
        )

        return {
            "success": True,
            "textured_mesh": low_unwrapped,
            "texture_filename": output_texture_path.name
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

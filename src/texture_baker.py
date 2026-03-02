"""
Texture Baking : transfert de texture High-Poly → Low-Poly via KDTree spatial.

Pipeline :
  1. Charger le high poly (GLB TRELLIS) avec sa texture + UVs
  2. Unwrap LSCM du low poly (nouveaux UVs propres)
  3. KDTree : pour chaque vertex low poly → vertex high poly le plus proche
  4. Rasteriser la nouvelle texture en interpolant les couleurs par triangle
  5. Retourner le low poly avec nouveaux UVs + texture bakée
"""

import numpy as np
import trimesh
from pathlib import Path
from typing import Dict, Any


def _sample_texture(tex_arr: np.ndarray, uv: np.ndarray) -> np.ndarray:
    """
    Sample une couleur depuis un tableau texture (H, W, C) avec des coordonnées UV.
    uv : array (N, 2) en [0,1]
    Retourne : (N, C)
    """
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
    Rasterise un triangle dans la texture bakée par interpolation barycentrique.
    uv* : (2,) en [0,1]
    c*  : (3,) couleur RGB uint8
    """
    # Convertir UVs en coordonnées pixel
    p0 = np.array([uv0[0] * texture_size, (1.0 - uv0[1]) * texture_size])
    p1 = np.array([uv1[0] * texture_size, (1.0 - uv1[1]) * texture_size])
    p2 = np.array([uv2[0] * texture_size, (1.0 - uv2[1]) * texture_size])

    # Bounding box du triangle en pixels
    min_x = max(0, int(min(p0[0], p1[0], p2[0])))
    max_x = min(texture_size - 1, int(max(p0[0], p1[0], p2[0])) + 1)
    min_y = max(0, int(min(p0[1], p1[1], p2[1])))
    max_y = min(texture_size - 1, int(max(p0[1], p1[1], p2[1])) + 1)

    if min_x >= max_x or min_y >= max_y:
        return

    # Dénominateur barycentrique
    denom = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
    if abs(denom) < 1e-8:
        return

    # Grille de pixels dans la bounding box
    xs = np.arange(min_x, max_x + 1)
    ys = np.arange(min_y, max_y + 1)
    gx, gy = np.meshgrid(xs + 0.5, ys + 0.5)
    gx = gx.ravel()
    gy = gy.ravel()

    # Coordonnées barycentriques
    w0 = ((p1[1] - p2[1]) * (gx - p2[0]) + (p2[0] - p1[0]) * (gy - p2[1])) / denom
    w1 = ((p2[1] - p0[1]) * (gx - p2[0]) + (p0[0] - p2[0]) * (gy - p2[1])) / denom
    w2 = 1.0 - w0 - w1

    # Garder uniquement les pixels à l'intérieur du triangle
    mask = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
    if not np.any(mask):
        return

    gx_m = gx[mask].astype(int)
    gy_m = gy[mask].astype(int)
    w0_m = w0[mask, np.newaxis]
    w1_m = w1[mask, np.newaxis]
    w2_m = w2[mask, np.newaxis]

    # Interpoler la couleur
    colors = (w0_m * c0 + w1_m * c1 + w2_m * c2).clip(0, 255).astype(np.uint8)
    baked[gy_m, gx_m] = colors


def bake_texture(
    high_poly_glb: Path,
    low_poly_mesh: trimesh.Trimesh,
    output_texture_path: Path,
    texture_size: int = 1024
) -> Dict[str, Any]:
    """
    Bake la texture du high poly (GLB TRELLIS) sur le low poly (mesh retopo).

    Args:
        high_poly_glb      : GLB TRELLIS original avec texture + UVs
        low_poly_mesh      : Trimesh du mesh retopologisé (sans texture)
        output_texture_path: Chemin PNG de sortie
        texture_size       : Résolution de la texture bakée (défaut 1024)

    Returns:
        dict : success, textured_mesh, texture_filename, error
    """
    from PIL import Image

    try:
        # 1. Charger le high poly et extraire texture + UVs
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

        # 2. Unwrap LSCM du low poly
        print(f"[BAKING] Unwrapping low poly ({len(low_poly_mesh.vertices)}v)...")
        low_unwrapped = low_poly_mesh.unwrap()

        if not hasattr(low_unwrapped.visual, 'uv') or low_unwrapped.visual.uv is None:
            return {"success": False, "error": "LSCM unwrap failed: no UVs produced"}

        low_uv = np.array(low_unwrapped.visual.uv)       # (M, 2)

        # 3. KDTree : vertex low poly → vertex high poly le plus proche
        print(f"[BAKING] Building KDTree on {len(high_mesh.vertices)} vertices...")
        from scipy.spatial import KDTree
        tree = KDTree(high_mesh.vertices)
        _, indices = tree.query(low_poly_mesh.vertices)   # indices shape (M,)

        # 4. Couleurs des vertices high poly via leurs UVs + texture
        high_uv_for_low = high_uv[indices]                # (M, 2) UVs high poly correspondants
        vertex_colors = _sample_texture(tex_arr, high_uv_for_low).astype(np.float32)  # (M, 3)

        # 5. Rasteriser la texture bakée triangle par triangle
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

        # 6. Sauvegarder la texture PNG
        baked_img = Image.fromarray(baked)
        baked_img.save(str(output_texture_path))
        print(f"[BAKING] Texture saved: {output_texture_path.name}")

        # 7. Assigner la texture bakée au low poly
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

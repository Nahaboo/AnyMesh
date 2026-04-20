"""
3D mesh simplification using pyfqmr Quadric Error Metric (QEM). GLB-first.

When preserve_texture=True: pyfqmr simplifies geometry, then vertex colors
are sampled from the original texture via closest-point + barycentric projection.
No LSCM, no rasterization — fast and works on non-watertight meshes.
"""

from pathlib import Path
from typing import Dict, Any
import trimesh
import numpy as np
import pyfqmr


def _sample_vertex_colors(
    high_poly: trimesh.Trimesh,
    simplified_verts: np.ndarray,
) -> np.ndarray | None:
    """
    Sample colors from high_poly texture for each vertex in simplified_verts.
    Uses closest-point projection + barycentric interpolation.
    Returns (N, 4) RGBA uint8 array, or None if high_poly has no texture.
    """
    visual = high_poly.visual
    if not hasattr(visual, 'uv') or visual.uv is None:
        return None
    if not hasattr(visual, 'material') or visual.material is None:
        return None
    if not hasattr(visual.material, 'baseColorTexture') or \
       visual.material.baseColorTexture is None:
        return None

    tex_arr = np.array(visual.material.baseColorTexture.convert('RGBA'))
    H, W = tex_arr.shape[:2]
    high_uv = np.array(visual.uv)

    print(f"[SIMPLIFY] Projecting {len(simplified_verts)} vertices onto high-poly surface...")
    closest_pts, _, tri_ids = trimesh.proximity.closest_point(high_poly, simplified_verts)
    tri_verts = high_poly.triangles[tri_ids]                           # (N, 3, 3)
    bary = trimesh.triangles.points_to_barycentric(tri_verts, closest_pts)  # (N, 3)
    face_uvs = high_uv[high_poly.faces[tri_ids]]                      # (N, 3, 2)
    uv_interp = (bary[:, :, np.newaxis] * face_uvs).sum(axis=1)       # (N, 2)
    np.nan_to_num(uv_interp, copy=False, nan=0.0)

    px = (uv_interp[:, 0] * W).astype(int) % W
    py = ((1.0 - uv_interp[:, 1]) * H).astype(int) % H
    colors = tex_arr[py, px]                                           # (N, 4)

    return colors


def simplify_mesh_glb(
    input_path: Path,
    output_path: Path,
    target_triangles: int = None,
    reduction_ratio: float = None,
    preserve_texture: bool = False,
    temp_dir: Path = Path("data/temp")
) -> Dict[str, Any]:
    """
    Simplify a GLB using Quadric Error Metric (pyfqmr).

    preserve_texture=True: samples vertex colors from original texture via
    closest-point projection after simplification. No LSCM, no rasterization.
    target_triangles takes priority over reduction_ratio.
    """
    try:
        if not input_path.exists():
            return {'success': False, 'error': f"File not found: {input_path}"}

        if target_triangles is None and reduction_ratio is None:
            return {'success': False, 'error': "Specify target_triangles or reduction_ratio"}

        loaded = trimesh.load(str(input_path))

        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if not meshes:
                return {'success': False, 'error': 'Empty scene, no geometry'}
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            return {'success': False, 'error': 'No valid vertices'}
        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            return {'success': False, 'error': 'No valid faces'}

        has_textures = (
            hasattr(mesh, 'visual') and
            hasattr(mesh.visual, 'material') and
            mesh.visual.material is not None
        )

        original_vertices = len(mesh.vertices)
        original_triangles = len(mesh.faces)

        if target_triangles is None:
            target_triangles = int(original_triangles * (1 - reduction_ratio))
        target_triangles = max(4, min(int(target_triangles), original_triangles))

        # pyfqmr: geometry-only QEM, preserve_border=True for non-watertight meshes
        simplifier = pyfqmr.Simplify()
        simplifier.setMesh(
            mesh.vertices.astype(np.float64),
            mesh.faces.astype(np.int32)
        )
        simplifier.simplify_mesh(
            target_count=target_triangles,
            aggressiveness=7,
            preserve_border=True,
            verbose=False,
        )
        verts, faces, _ = simplifier.getMesh()
        mesh_simplified = trimesh.Trimesh(vertices=verts, faces=faces, process=False)

        texture_transferred = False
        if preserve_texture and has_textures:
            colors = _sample_vertex_colors(mesh, verts)
            if colors is not None:
                mesh_simplified.visual = trimesh.visual.ColorVisuals(
                    mesh=mesh_simplified,
                    vertex_colors=colors
                )
                texture_transferred = True
                print(f"[SIMPLIFY] Vertex colors sampled: {len(verts)} vertices")
            else:
                print("[SIMPLIFY] No texture found — exporting without colors")

        mesh_simplified.export(str(output_path), file_type='glb')

        simplified_vertices = len(mesh_simplified.vertices)
        simplified_triangles = len(mesh_simplified.faces)

        return {
            'success': True,
            'original_vertices': original_vertices,
            'original_triangles': original_triangles,
            'simplified_vertices': simplified_vertices,
            'simplified_triangles': simplified_triangles,
            'vertices_ratio': 1 - (simplified_vertices / original_vertices) if original_vertices > 0 else 0,
            'triangles_ratio': 1 - (simplified_triangles / original_triangles) if original_triangles > 0 else 0,
            'vertices_removed': original_vertices - simplified_vertices,
            'triangles_removed': original_triangles - simplified_triangles,
            'output_file': str(output_path),
            'output_size': output_path.stat().st_size,
            'has_textures': has_textures,
            'textures_lost': has_textures and not texture_transferred,
            'texture_transferred': texture_transferred,
            'is_watertight': bool(mesh_simplified.is_watertight)
        }

    except Exception as e:
        return {'success': False, 'error': f"Erreur simplification GLB: {str(e)}"}

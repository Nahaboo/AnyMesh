"""
UV Unwrapping via trimesh LSCM (Least Squares Conformal Maps).
Pipeline: GLB -> trimesh -> mesh.unwrap() -> GLB avec UVs propres.
"""
import logging
import numpy as np
import trimesh
from pathlib import Path

logger = logging.getLogger(__name__)


def unwrap_uv(input_path: Path, output_path: Path) -> dict:
    """
    UV unwrap via native trimesh LSCM.
    Returns: success, output_filename, vertices_count, faces_count, uv_coverage.
    """
    try:
        loaded = trimesh.load(str(input_path), force='mesh')
    except Exception as e:
        return {'success': False, 'error': f'Failed to load mesh: {e}'}

    if not isinstance(loaded, trimesh.Trimesh):
        return {'success': False, 'error': 'Invalid mesh after loading'}

    mesh = loaded
    n_verts = len(mesh.vertices)
    n_faces = len(mesh.faces)

    # Check for non-manifold geometry
    if not mesh.is_winding_consistent:
        logger.warning(f"[UV_UNWRAP] Mesh winding inconsistent: {input_path.name}")

    if not mesh.is_watertight:
        logger.warning(f"[UV_UNWRAP] Mesh is not watertight, unwrap may have seams: {input_path.name}")

    logger.info(f"[UV_UNWRAP] Starting LSCM unwrap: {input_path.name} ({n_verts}v / {n_faces}f)")

    try:
        unwrapped = mesh.unwrap()
    except Exception as e:
        return {'success': False, 'error': f'LSCM unwrap failed: {e}'}

    if unwrapped is None or not hasattr(unwrapped, 'visual'):
        return {'success': False, 'error': 'LSCM produced no UVs'}

    # Compute uv_coverage: % of [0,1]^2 space used
    uv_coverage = 0.0
    try:
        if hasattr(unwrapped.visual, 'uv') and unwrapped.visual.uv is not None:
            uvs = unwrapped.visual.uv
            # UV triangle area / total [0,1]^2 area
            uv_faces = unwrapped.faces
            v0 = uvs[uv_faces[:, 0]]
            v1 = uvs[uv_faces[:, 1]]
            v2 = uvs[uv_faces[:, 2]]
            cross = (v1 - v0)[:, 0] * (v2 - v0)[:, 1] - (v1 - v0)[:, 1] * (v2 - v0)[:, 0]
            area = float(np.sum(np.abs(cross)) / 2.0)
            uv_coverage = min(round(area * 100, 1), 100.0)
    except Exception:
        uv_coverage = 0.0

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        unwrapped.export(str(output_path), file_type='glb')
    except Exception as e:
        return {'success': False, 'error': f'GLB export failed: {e}'}

    logger.info(f"[UV_UNWRAP] Done: {output_path.name} | coverage={uv_coverage}%")

    return {
        'success': True,
        'output_file': str(output_path),
        'output_filename': output_path.name,
        'vertices_count': len(unwrapped.vertices),
        'faces_count': len(unwrapped.faces),
        'uv_coverage': uv_coverage,
    }

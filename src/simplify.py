"""
3D mesh simplification using pyfqmr Quadric Error Metric (QEM). GLB-first.
"""

from pathlib import Path
from typing import Dict, Any
import trimesh
import numpy as np
import pyfqmr


def simplify_mesh_glb(
    input_path: Path,
    output_path: Path,
    target_triangles: int = None,
    reduction_ratio: float = None
) -> Dict[str, Any]:
    """
    Simplify a GLB using Quadric Error Metric (pyfqmr).

    Textures are always lost: UVs become invalid after geometry modification.
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

        had_textures = (
            hasattr(mesh, 'visual') and
            hasattr(mesh.visual, 'material') and
            mesh.visual.material is not None
        )

        original_vertices = len(mesh.vertices)
        original_triangles = len(mesh.faces)

        if target_triangles is None:
            target_triangles = int(original_triangles * (1 - reduction_ratio))

        target_triangles = max(4, min(int(target_triangles), original_triangles))

        # preserve_border=True protects open boundary edges, unlike trimesh.simplify_quadric_decimation
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
            'had_textures': had_textures,
            'textures_lost': had_textures
        }

    except Exception as e:
        return {'success': False, 'error': f"Erreur simplification GLB: {str(e)}"}

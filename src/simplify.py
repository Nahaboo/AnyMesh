"""
Module de simplification de maillages 3D — GLB-First via pyfqmr QEM
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
    Simplifie un GLB directement avec l'algorithme Quadric Error Metric de Trimesh.

    ATTENTION: Les textures sont perdues lors de la simplification
    car les UVs deviennent invalides après modification de la géométrie.

    Args:
        input_path: Chemin vers le fichier GLB d'entrée
        output_path: Chemin vers le fichier GLB de sortie
        target_triangles: Nombre cible de triangles (prioritaire sur reduction_ratio)
        reduction_ratio: Ratio de réduction (0.0 - 1.0), ex: 0.5 = garder 50% des faces

    Returns:
        Dictionnaire contenant les statistiques de simplification
    """
    try:
        if not input_path.exists():
            return {'success': False, 'error': f"Fichier introuvable: {input_path}"}

        if target_triangles is None and reduction_ratio is None:
            return {'success': False, 'error': "Spécifier target_triangles ou reduction_ratio"}

        # Charger le GLB avec Trimesh
        loaded = trimesh.load(str(input_path))

        # Gérer les Scenes (plusieurs meshes dans un GLB)
        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if not meshes:
                return {'success': False, 'error': 'Scene vide, aucune geometrie'}
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            return {'success': False, 'error': 'Pas de vertices valides'}
        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            return {'success': False, 'error': 'Pas de faces valides'}

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

        # pyfqmr : preserve_border=True protège les arêtes ouvertes (boundary edges)
        # ce que trimesh.simplify_quadric_decimation ne supporte pas
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

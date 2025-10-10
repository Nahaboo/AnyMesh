"""
Module de simplification de maillages 3D avec Open3D
"""

import open3d as o3d
import copy
from pathlib import Path
from typing import Dict, Any


def simplify_mesh(
    input_path: Path,
    output_path: Path,
    target_triangles: int = None,
    reduction_ratio: float = None,
    preserve_boundary: bool = True
) -> Dict[str, Any]:
    """
    Simplifie un maillage 3D en reduisant le nombre de triangles.

    Args:
        input_path: Chemin vers le fichier d'entree
        output_path: Chemin vers le fichier de sortie
        target_triangles: Nombre cible de triangles (prioritaire sur reduction_ratio)
        reduction_ratio: Ratio de reduction (0.0 - 1.0), ex: 0.5 = reduction de 50%
        preserve_boundary: Preserve les bords du maillage

    Returns:
        Dictionnaire contenant les statistiques de simplification
    """
    # Chargement du maillage original
    mesh_original = o3d.io.read_triangle_mesh(str(input_path))

    if not mesh_original.has_vertices():
        raise ValueError("Le maillage ne contient pas de vertices")

    original_vertices = len(mesh_original.vertices)
    original_triangles = len(mesh_original.triangles)

    # Calcul du nombre cible de triangles
    if target_triangles is None:
        if reduction_ratio is None:
            reduction_ratio = 0.5  # Par defaut, reduction de 50%
        target_triangles = int(original_triangles * (1 - reduction_ratio))

    # IMPORTANT: Copie profonde pour preserver l'original
    mesh_simplified = copy.deepcopy(mesh_original)

    # Simplification avec l'algorithme Quadric Error Metric
    mesh_simplified = mesh_simplified.simplify_quadric_decimation(
        target_number_of_triangles=target_triangles
    )

    # Optionnel: recalcul des normales si necessaire
    if mesh_original.has_vertex_normals():
        mesh_simplified.compute_vertex_normals()

    # Sauvegarde du maillage simplifie
    success = o3d.io.write_triangle_mesh(str(output_path), mesh_simplified)

    if not success:
        raise IOError(f"Impossible de sauvegarder le maillage dans {output_path}")

    # Statistiques
    simplified_vertices = len(mesh_simplified.vertices)
    simplified_triangles = len(mesh_simplified.triangles)

    stats = {
        "original": {
            "vertices": original_vertices,
            "triangles": original_triangles
        },
        "simplified": {
            "vertices": simplified_vertices,
            "triangles": simplified_triangles
        },
        "reduction": {
            "vertices_ratio": 1 - (simplified_vertices / original_vertices),
            "triangles_ratio": 1 - (simplified_triangles / original_triangles),
            "vertices_removed": original_vertices - simplified_vertices,
            "triangles_removed": original_triangles - simplified_triangles
        },
        "output_file": str(output_path),
        "output_size": output_path.stat().st_size
    }

    return stats

"""
Module de simplification de maillages 3D avec Open3D
"""

import open3d as o3d
import numpy as np
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
    Simplifie un maillage 3D en réduisant le nombre de triangles avec Open3D.

    Utilise l'algorithme Quadric Error Metric (QEM) de Garland & Heckbert (1997).

    Args:
        input_path: Chemin vers le fichier d'entrée
        output_path: Chemin vers le fichier de sortie
        target_triangles: Nombre cible de triangles (prioritaire sur reduction_ratio)
        reduction_ratio: Ratio de réduction (0.0 - 1.0), ex: 0.5 = réduction de 50%
        preserve_boundary: Préserve les bords du maillage (boundary_weight=3.0 si True)

    Returns:
        Dictionnaire contenant les statistiques de simplification ou erreur
    """
    try:
        # Vérifier que le fichier existe
        if not input_path.exists():
            return {
                'success': False,
                'error': f"Le fichier d'entrée n'existe pas: {input_path}"
            }

        # Vérifier qu'au moins un paramètre de réduction est fourni
        if target_triangles is None and reduction_ratio is None:
            return {
                'success': False,
                'error': "Vous devez spécifier target_triangles ou reduction_ratio"
            }

        # Chargement du maillage original avec Open3D
        mesh_original = o3d.io.read_triangle_mesh(str(input_path))

        if not mesh_original.has_vertices() or len(mesh_original.vertices) == 0:
            return {
                'success': False,
                'error': "Le maillage ne contient pas de vertices valides"
            }

        original_vertices = len(mesh_original.vertices)
        original_triangles = len(mesh_original.triangles)

        # Calcul du nombre cible de triangles
        if target_triangles is None:
            target_triangles = int(original_triangles * (1 - reduction_ratio))

        # Convertir en int si nécessaire
        target_triangles = int(target_triangles)

        # S'assurer que target_triangles est valide (minimum 4 faces pour un tétraèdre)
        target_triangles = max(4, min(target_triangles, original_triangles))

        # Déterminer le boundary_weight en fonction de preserve_boundary
        # boundary_weight > 1.0 augmente le coût de fusion des vertices de bord
        # 3.0 est une bonne valeur pour préserver les bords sans trop rigidifier
        boundary_weight = 3.0 if preserve_boundary else 1.0

        # Simplification avec l'algorithme Quadric Error Metric (Open3D)
        # - target_number_of_triangles: nombre de triangles cibles
        # - maximum_error: erreur max autorisée (inf = pas de limite)
        # - boundary_weight: poids pour préserver les bords (>1.0 = préservation)
        mesh_simplified = mesh_original.simplify_quadric_decimation(
            target_number_of_triangles=target_triangles,
            maximum_error=float('inf'),
            boundary_weight=boundary_weight
        )

        # Recalcul des normales pour un meilleur rendu
        mesh_simplified.compute_vertex_normals()

        # Sauvegarde du maillage simplifié
        o3d.io.write_triangle_mesh(str(output_path), mesh_simplified)

        # Statistiques
        simplified_vertices = len(mesh_simplified.vertices)
        simplified_triangles = len(mesh_simplified.triangles)

        stats = {
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
            'output_size': output_path.stat().st_size
        }

        return stats

    except Exception as e:
        return {
            'success': False,
            'error': f"Erreur lors de la simplification: {str(e)}"
        }

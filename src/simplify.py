"""
Module de simplification de maillages 3D avec trimesh
"""

import trimesh
import numpy as np
from pathlib import Path
from typing import Dict, Any
import copy

def simplify_mesh(
    input_path: Path,
    output_path: Path,
    target_triangles: int = None,
    reduction_ratio: float = None,
    preserve_boundary: bool = True
) -> Dict[str, Any]:
    """
    Simplifie un maillage 3D en réduisant le nombre de triangles.

    Args:
        input_path: Chemin vers le fichier d'entrée
        output_path: Chemin vers le fichier de sortie
        target_triangles: Nombre cible de triangles (prioritaire sur reduction_ratio)
        reduction_ratio: Ratio de réduction (0.0 - 1.0), ex: 0.5 = réduction de 50%
        preserve_boundary: Préserve les bords du maillage

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

        # Chargement du maillage original avec trimesh
        mesh_original = trimesh.load(str(input_path))

        if not hasattr(mesh_original, 'vertices') or len(mesh_original.vertices) == 0:
            return {
                'success': False,
                'error': "Le maillage ne contient pas de vertices valides"
            }

        original_vertices = len(mesh_original.vertices)
        original_triangles = len(mesh_original.faces)

        # Calcul du nombre cible de triangles
        if target_triangles is None:
            target_triangles = int(original_triangles * (1 - reduction_ratio))

        # Convertir en int si nécessaire
        target_triangles = int(target_triangles)

        # S'assurer que target_triangles est valide (minimum 4 faces pour un tétraèdre)
        target_triangles = max(4, min(target_triangles, original_triangles))

        # Création d'une copie profonde
        mesh_simplified = copy.deepcopy(mesh_original)

        # Simplification avec l'algorithme Quadric Error Metric
        # Trimesh utilise face_count (nombre de faces cibles) comme paramètre
        mesh_simplified = mesh_simplified.simplify_quadric_decimation(
            face_count=target_triangles
        )

        # Optionnel: recalcul des normales si nécessaire
        if hasattr(mesh_original, 'vertex_normals') and mesh_original.vertex_normals.any():
            mesh_simplified.vertex_normals = mesh_simplified.vertex_normals

        # Sauvegarde du maillage simplifié
        mesh_simplified.export(str(output_path))

        # Statistiques
        simplified_vertices = len(mesh_simplified.vertices)
        simplified_triangles = len(mesh_simplified.faces)

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

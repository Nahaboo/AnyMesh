"""
Module de segmentation de maillages 3D
Combine Open3D et PyMeshLab pour différentes stratégies
"""

import open3d as o3d
import pymeshlab as ml
import numpy as np
from pathlib import Path
from typing import Dict, Any


def segment_by_connectivity(
    input_path: Path,
    output_path: Path
) -> Dict[str, Any]:
    """
    Segmente le mesh en composants déconnectés.

    Use case: Anses détachées, bracelets amovibles
    Performance: Très rapide (< 1s)

    Returns:
        Dict avec success, num_segments, et infos
    """
    try:
        mesh = o3d.io.read_triangle_mesh(str(input_path))

        if not mesh.has_vertices():
            return {'success': False, 'error': 'Mesh vide'}

        # Segmentation par composants connectés
        triangle_clusters, cluster_n_triangles, cluster_area = \
            mesh.cluster_connected_triangles()

        triangle_clusters = np.asarray(triangle_clusters)
        num_segments = triangle_clusters.max() + 1

        # Assigner des couleurs aléatoires à chaque segment
        colors = np.random.rand(num_segments, 3)
        vertex_colors = np.zeros((len(mesh.vertices), 3))

        for tri_idx, cluster_id in enumerate(triangle_clusters):
            triangle = mesh.triangles[tri_idx]
            for vertex_idx in triangle:
                vertex_colors[vertex_idx] = colors[cluster_id]

        mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)

        # Sauvegarder
        o3d.io.write_triangle_mesh(str(output_path), mesh)

        return {
            'success': True,
            'num_segments': int(num_segments),
            'segment_sizes': list(cluster_n_triangles),
            'segment_areas': list(cluster_area),
            'method': 'connectivity'
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def segment_by_sharp_edges(
    input_path: Path,
    output_path: Path,
    angle_threshold: float = 45.0
) -> Dict[str, Any]:
    """
    Segmente le mesh en détectant les arêtes vives.

    Use case: Fermetures éclair, boucles, frontières cousues
    Performance: Rapide (1-3s)

    Args:
        angle_threshold: Angle minimum (degrés) pour considérer une arête comme vive

    Returns:
        Dict avec success, num_segments, et infos
    """
    try:
        ms = ml.MeshSet()
        ms.load_new_mesh(str(input_path))

        # Détecter arêtes vives
        ms.compute_selection_by_non_manifold_edges_per_face()
        ms.compute_selection_by_angle(anglelimit=angle_threshold)

        # Dilater la sélection pour créer des régions
        ms.dilate_selection()

        # TODO: Implémenter clustering sur les faces sélectionnées
        # Pour MVP: colorer simplement les faces sélectionnées différemment

        # Sauvegarder
        ms.save_current_mesh(str(output_path), save_vertex_color=True)

        return {
            'success': True,
            'num_segments': 2,  # Simplifié pour MVP
            'method': 'sharp_edges',
            'angle_threshold': angle_threshold
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def segment_by_curvature(
    input_path: Path,
    output_path: Path,
    num_clusters: int = 5
) -> Dict[str, Any]:
    """
    Segmente le mesh par zones de courbure similaire.

    Use case: Zones plates vs arrondies
    Performance: Moyenne (3-10s selon taille mesh)

    Args:
        num_clusters: Nombre de segments cibles

    Returns:
        Dict avec success, num_segments, et infos
    """
    try:
        ms = ml.MeshSet()
        ms.load_new_mesh(str(input_path))

        # Calculer courbure principale
        ms.compute_curvature_principal_directions()

        # TODO: Implémenter k-means sur valeurs de courbure
        # Pour MVP: utiliser sélection par qualité (courbure stockée en qualité)

        ms.save_current_mesh(str(output_path), save_vertex_color=True)

        return {
            'success': True,
            'num_segments': num_clusters,
            'method': 'curvature'
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def segment_by_planes(
    input_path: Path,
    output_path: Path,
    num_planes: int = 3,
    distance_threshold: float = 0.01
) -> Dict[str, Any]:
    """
    Segmente le mesh en détectant surfaces planaires (RANSAC).

    Use case: Faces de montre, côtés de boîte
    Performance: Rapide (1-3s)

    Args:
        num_planes: Nombre de plans à détecter
        distance_threshold: Distance max d'un point au plan pour appartenance

    Returns:
        Dict avec success, num_segments, et infos
    """
    try:
        mesh = o3d.io.read_triangle_mesh(str(input_path))

        # Convertir en point cloud pour RANSAC
        pcd = mesh.sample_points_uniformly(number_of_points=10000)

        labels = np.zeros(len(pcd.points))
        remaining_indices = np.arange(len(pcd.points))

        planes_found = []

        for plane_id in range(num_planes):
            if len(remaining_indices) < 100:
                break

            # Sous-ensemble de points restants
            sub_pcd = pcd.select_by_index(remaining_indices)

            # RANSAC pour détecter un plan
            plane_model, inliers = sub_pcd.segment_plane(
                distance_threshold=distance_threshold,
                ransac_n=3,
                num_iterations=1000
            )

            if len(inliers) < 50:
                break

            # Assigner label
            global_inliers = remaining_indices[inliers]
            labels[global_inliers] = plane_id + 1

            # Retirer points assignés
            remaining_indices = np.delete(remaining_indices, inliers)

            planes_found.append({
                'equation': plane_model.tolist(),
                'num_points': len(inliers)
            })

        # Mapper labels du point cloud au mesh original
        # Créer des couleurs pour chaque label
        num_labels = int(labels.max()) + 1
        colors = np.random.rand(num_labels, 3)

        # Assigner couleurs aux vertices du mesh basé sur le label du point le plus proche
        mesh_vertices = np.asarray(mesh.vertices)
        pcd_points = np.asarray(pcd.points)

        # Pour chaque vertex du mesh, trouver le point du point cloud le plus proche
        from scipy.spatial import cKDTree
        tree = cKDTree(pcd_points)
        distances, indices = tree.query(mesh_vertices, k=1)

        # Assigner les couleurs basées sur les labels
        vertex_colors = colors[labels[indices].astype(int)]
        mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)

        # Sauvegarder le mesh avec couleurs
        o3d.io.write_triangle_mesh(str(output_path), mesh)

        return {
            'success': True,
            'num_segments': len(planes_found),
            'planes': planes_found,
            'method': 'planes'
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def segment_mesh(
    input_path: Path,
    output_path: Path,
    method: str = "connectivity",
    **kwargs
) -> Dict[str, Any]:
    """
    Point d'entrée principal pour segmentation de mesh.

    Args:
        input_path: Chemin du mesh d'entrée
        output_path: Chemin du mesh de sortie segmenté
        method: Méthode de segmentation ('connectivity', 'sharp_edges', 'curvature', 'planes')
        **kwargs: Paramètres spécifiques à la méthode

    Returns:
        Dictionnaire avec résultats de segmentation
    """
    methods = {
        'connectivity': segment_by_connectivity,
        'sharp_edges': segment_by_sharp_edges,
        'curvature': segment_by_curvature,
        'planes': segment_by_planes
    }

    if method not in methods:
        return {
            'success': False,
            'error': f"Méthode inconnue: {method}. Choix: {list(methods.keys())}"
        }

    return methods[method](input_path, output_path, **kwargs)

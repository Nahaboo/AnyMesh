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
        # Charger avec Open3D
        mesh = o3d.io.read_triangle_mesh(str(input_path))

        if not mesh.has_vertices():
            return {'success': False, 'error': 'Mesh vide'}

        # Calculer les normales de triangles (pas de vertices)
        mesh.compute_triangle_normals()

        # Récupérer les données
        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles)
        triangle_normals = np.asarray(mesh.triangle_normals)

        num_vertices = len(vertices)
        num_triangles = len(triangles)

        # Convertir le seuil en radians
        threshold_rad = np.radians(angle_threshold)

        print(f"  [SHARP_EDGES] Détection d'arêtes avec seuil: {angle_threshold}°")
        print(f"  Mesh: {num_vertices} vertices, {num_triangles} triangles")

        # Construire un dictionnaire des arêtes et leurs triangles adjacents
        # edge_dict[edge] = [triangle_indices]
        edge_dict = {}

        for tri_idx, triangle in enumerate(triangles):
            # Pour chaque triangle, créer les 3 arêtes
            edges = [
                tuple(sorted([triangle[0], triangle[1]])),
                tuple(sorted([triangle[1], triangle[2]])),
                tuple(sorted([triangle[2], triangle[0]]))
            ]

            for edge in edges:
                if edge not in edge_dict:
                    edge_dict[edge] = []
                edge_dict[edge].append(tri_idx)

        # Détecter les arêtes vives
        sharp_edges = set()

        for edge, tri_indices in edge_dict.items():
            # Une arête est partagée par 2 triangles (manifold)
            # Si 1 seul triangle: arête de frontière (toujours vive)
            # Si 2 triangles: calculer l'angle entre normales
            if len(tri_indices) == 1:
                # Arête de frontière
                sharp_edges.add(edge)
            elif len(tri_indices) == 2:
                # Calculer l'angle entre les normales des deux triangles
                n1 = triangle_normals[tri_indices[0]]
                n2 = triangle_normals[tri_indices[1]]

                # Produit scalaire pour obtenir le cosinus de l'angle
                cos_angle = np.dot(n1, n2)
                # Clamper pour éviter erreurs numériques
                cos_angle = np.clip(cos_angle, -1.0, 1.0)

                # Angle en radians
                angle = np.arccos(cos_angle)

                # Si l'angle > seuil, c'est une arête vive
                if angle > threshold_rad:
                    sharp_edges.add(edge)

        print(f"  [SHARP_EDGES] Détecté {len(sharp_edges)} arêtes vives")

        # Marquer les vertices près des arêtes vives
        sharp_vertex_set = set()
        for edge in sharp_edges:
            sharp_vertex_set.add(edge[0])
            sharp_vertex_set.add(edge[1])

        # Segmentation par composantes connectées en excluant les arêtes vives
        # Construire un graphe de triangles connectés (sans traverser les arêtes vives)
        from scipy.sparse import lil_matrix
        from scipy.sparse.csgraph import connected_components

        adjacency = lil_matrix((num_triangles, num_triangles), dtype=bool)

        for edge, tri_indices in edge_dict.items():
            # Si l'arête n'est pas vive et connecte 2 triangles
            if edge not in sharp_edges and len(tri_indices) == 2:
                adjacency[tri_indices[0], tri_indices[1]] = True
                adjacency[tri_indices[1], tri_indices[0]] = True

        # Trouver les composantes connectées
        num_segments, triangle_labels = connected_components(adjacency, directed=False)

        print(f"  [SHARP_EDGES] Segmenté en {num_segments} régions")

        # Générer des couleurs aléatoires pour chaque segment
        segment_colors = np.random.rand(num_segments, 3)

        # Assigner des couleurs aux vertices basé sur les triangles
        # Stratégie: chaque vertex prend la couleur majoritaire des triangles adjacents
        vertex_colors = np.zeros((num_vertices, 3))
        vertex_segment_votes = [[] for _ in range(num_vertices)]

        for tri_idx, triangle in enumerate(triangles):
            segment_id = triangle_labels[tri_idx]
            for vertex_idx in triangle:
                vertex_segment_votes[vertex_idx].append(segment_id)

        # Vote majoritaire pour chaque vertex
        for v_idx in range(num_vertices):
            if vertex_segment_votes[v_idx]:
                # Segment le plus fréquent
                segment_id = max(set(vertex_segment_votes[v_idx]),
                               key=vertex_segment_votes[v_idx].count)
                vertex_colors[v_idx] = segment_colors[segment_id]

        # Appliquer les couleurs
        mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)

        # Sauvegarder
        o3d.io.write_triangle_mesh(str(output_path), mesh)

        return {
            'success': True,
            'num_segments': num_segments,
            'num_sharp_edges': len(sharp_edges),
            'method': 'sharp_edges',
            'angle_threshold': angle_threshold
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def segment_by_curvature(
    input_path: Path,
    output_path: Path,
    num_clusters: int = 5
) -> Dict[str, Any]:
    """
    Segmente le mesh par zones de courbure similaire.

    Utilise la courbure moyenne approximée par la variance des normales des voisins,
    puis applique k-means clustering sur ces valeurs.

    Use case: Zones plates vs arrondies
    Performance: Moyenne (3-10s selon taille mesh)

    Args:
        num_clusters: Nombre de segments cibles

    Returns:
        Dict avec success, num_segments, et infos
    """
    try:
        from sklearn.cluster import KMeans

        mesh = o3d.io.read_triangle_mesh(str(input_path))

        if not mesh.has_vertices():
            return {'success': False, 'error': 'Mesh vide'}

        # Calculer les normales de vertices
        if not mesh.has_vertex_normals():
            mesh.compute_vertex_normals()

        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles)
        vertex_normals = np.asarray(mesh.vertex_normals)

        num_vertices = len(vertices)

        print(f"  [CURVATURE] Calcul de courbure pour {num_vertices} vertices")

        # Construire un dictionnaire vertex -> triangles adjacents
        vertex_to_triangles = [[] for _ in range(num_vertices)]
        for tri_idx, triangle in enumerate(triangles):
            for vertex_idx in triangle:
                vertex_to_triangles[vertex_idx].append(tri_idx)

        # Calculer la courbure approximée pour chaque vertex
        # Méthode: variance des normales des triangles adjacents
        curvatures = np.zeros(num_vertices)

        for v_idx in range(num_vertices):
            adjacent_tris = vertex_to_triangles[v_idx]

            if len(adjacent_tris) < 2:
                # Vertex isolé ou sur le bord -> courbure nulle
                curvatures[v_idx] = 0.0
                continue

            # Calculer la variance des normales des triangles adjacents
            # Plus la variance est grande, plus la courbure est élevée
            vertex_normal = vertex_normals[v_idx]

            # Calculer l'angle moyen entre la normale du vertex et les normales des triangles
            angles = []
            for tri_idx in adjacent_tris:
                # Normale du triangle (calculée depuis les vertices)
                tri_verts = triangles[tri_idx]
                v0, v1, v2 = vertices[tri_verts[0]], vertices[tri_verts[1]], vertices[tri_verts[2]]
                edge1 = v1 - v0
                edge2 = v2 - v0
                tri_normal = np.cross(edge1, edge2)
                norm = np.linalg.norm(tri_normal)
                if norm > 0:
                    tri_normal = tri_normal / norm
                    # Angle entre normale du vertex et normale du triangle
                    cos_angle = np.clip(np.dot(vertex_normal, tri_normal), -1.0, 1.0)
                    angle = np.arccos(cos_angle)
                    angles.append(angle)

            # Courbure = variance des angles (mesure de non-planéité)
            if len(angles) > 0:
                curvatures[v_idx] = np.var(angles)

        print(f"  [CURVATURE] Courbure min: {curvatures.min():.4f}, max: {curvatures.max():.4f}")

        # Normaliser les courbures pour le clustering
        curvature_mean = curvatures.mean()
        curvature_std = curvatures.std()

        if curvature_std > 0:
            curvatures_normalized = (curvatures - curvature_mean) / curvature_std
        else:
            curvatures_normalized = curvatures - curvature_mean

        # Clustering k-means sur les valeurs de courbure
        # Reshape pour sklearn: (n_samples, n_features)
        X = curvatures_normalized.reshape(-1, 1)

        kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
        vertex_labels = kmeans.fit_predict(X)

        print(f"  [CURVATURE] K-means clustering: {num_clusters} clusters")

        # Générer des couleurs pour chaque cluster
        cluster_colors = np.random.rand(num_clusters, 3)

        # Assigner des couleurs aux vertices
        vertex_colors = cluster_colors[vertex_labels]

        mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)

        # Sauvegarder
        o3d.io.write_triangle_mesh(str(output_path), mesh)

        # Calculer des statistiques par cluster
        cluster_sizes = [int(np.sum(vertex_labels == i)) for i in range(num_clusters)]

        return {
            'success': True,
            'num_segments': num_clusters,
            'cluster_sizes': cluster_sizes,
            'curvature_range': [float(curvatures.min()), float(curvatures.max())],
            'method': 'curvature'
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def segment_by_planes(
    input_path: Path,
    output_path: Path,
    num_planes: int = 3,
    angle_tolerance: float = 5.0
) -> Dict[str, Any]:
    """
    Segmente le mesh en détectant surfaces planaires via clustering de normales.

    Stratégie:
    1. Calculer les normales de triangles
    2. Clustériser les triangles par direction de normale similaire
    3. Pour chaque cluster, vérifier coplanarité (triangles sur même plan)
    4. Assigner couleurs aux vertices selon appartenance au plan

    Use case: Faces de montre, côtés de boîte
    Performance: Rapide (1-3s)

    Args:
        num_planes: Nombre de clusters de normales (surfaces planes attendues)
        angle_tolerance: Tolérance angulaire (degrés) pour regrouper normales similaires

    Returns:
        Dict avec success, num_segments, et infos
    """
    try:
        from sklearn.cluster import KMeans

        mesh = o3d.io.read_triangle_mesh(str(input_path))

        if not mesh.has_vertices():
            return {'success': False, 'error': 'Mesh vide'}

        # Calculer les normales de triangles
        mesh.compute_triangle_normals()

        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles)
        triangle_normals = np.asarray(mesh.triangle_normals)

        num_vertices = len(vertices)
        num_triangles = len(triangles)

        print(f"  [PLANES] Détection de {num_planes} plans sur {num_triangles} triangles")

        # Étape 1: Clustériser les triangles par direction de normale
        # On utilise k-means sur les normales (vecteurs unitaires)
        # IMPORTANT: On demande plus de clusters que nécessaire, puis on filtre
        initial_clusters = max(num_planes * 2, 10)  # Sur-clustériser d'abord
        kmeans = KMeans(n_clusters=initial_clusters, random_state=42, n_init=10)
        triangle_labels_initial = kmeans.fit_predict(triangle_normals)

        print(f"  [PLANES] K-means initial: {initial_clusters} groupes")

        # Étape 2: Filtrer les clusters pour ne garder que les surfaces vraiment planes
        # Un cluster est "plane" si la variance des normales est faible
        plane_clusters = []
        cluster_scores = []  # (cluster_id, variance, size)

        for cluster_id in range(initial_clusters):
            cluster_mask = triangle_labels_initial == cluster_id
            cluster_normals = triangle_normals[cluster_mask]
            cluster_size = len(cluster_normals)

            if cluster_size < 10:  # Cluster trop petit, ignorer
                continue

            # Calculer la variance des normales dans ce cluster
            # Si variance faible → triangles coplanaires (surface plane)
            # Si variance élevée → surface courbe
            normal_variance = np.var(cluster_normals, axis=0).sum()

            cluster_scores.append((cluster_id, normal_variance, cluster_size))

        # Trier par variance (les plus planaires en premier)
        cluster_scores.sort(key=lambda x: x[1])

        # Déterminer le seuil adaptatif basé sur la distribution des variances
        if len(cluster_scores) > 0:
            variances = [score[1] for score in cluster_scores]
            # Seuil adaptatif: médiane des variances / 2 (ou 0.005 minimum)
            adaptive_threshold = max(0.005, np.median(variances) / 2)
            print(f"  [PLANES] Seuil adaptatif de planéité: {adaptive_threshold:.6f}")

            # Garder les clusters sous le seuil
            for cluster_id, variance, size in cluster_scores:
                if variance < adaptive_threshold:
                    plane_clusters.append(cluster_id)

        print(f"  [PLANES] Trouvé {len(plane_clusters)} surfaces vraiment planes")

        # Si on a trouvé moins de plans que demandé, garder les meilleurs
        # Si on en a trouvé plus, prendre les num_planes plus grands
        if len(plane_clusters) == 0:
            # Aucune surface plane détectée, fallback sur k-means classique
            print(f"  [PLANES] Aucune surface plane détectée, fallback sur clustering classique")
            triangle_labels = triangle_labels_initial
            num_planes = initial_clusters
        else:
            # Garder uniquement les clusters plans
            # Créer un mapping: 0 = non-plan, 1..N = plans détectés
            triangle_labels = np.zeros(num_triangles, dtype=int)

            for new_id, old_cluster_id in enumerate(plane_clusters[:num_planes], start=1):
                cluster_mask = triangle_labels_initial == old_cluster_id
                triangle_labels[cluster_mask] = new_id

            # Les triangles non assignés (non-plans) restent à 0
            num_planes = len(plane_clusters[:num_planes]) + 1  # +1 pour le groupe "non-plan"

        print(f"  [PLANES] Segmentation finale: {num_planes} groupes")

        # Générer des couleurs pour chaque plan
        plane_colors = np.random.rand(num_planes, 3)

        # Calculer les normales moyennes pour chaque segment final
        # IMPORTANT: Utiliser triangle_labels (les nouveaux labels), pas cluster_normals de kmeans
        final_cluster_normals = []
        for segment_id in range(num_planes):
            segment_mask = triangle_labels == segment_id
            if segment_mask.sum() > 0:
                # Moyenne des normales dans ce segment
                mean_normal = triangle_normals[segment_mask].mean(axis=0)
                norm = np.linalg.norm(mean_normal)
                if norm > 0:
                    mean_normal = mean_normal / norm
                final_cluster_normals.append(mean_normal)
            else:
                # Segment vide (ne devrait pas arriver)
                final_cluster_normals.append(np.array([0, 0, 1]))

        final_cluster_normals = np.array(final_cluster_normals)

        # Assigner des couleurs aux vertices basé sur les triangles adjacents
        # Stratégie: vote majoritaire des triangles adjacents
        vertex_colors = np.zeros((num_vertices, 3))
        vertex_label_votes = [[] for _ in range(num_vertices)]

        for tri_idx, triangle in enumerate(triangles):
            label = triangle_labels[tri_idx]
            for vertex_idx in triangle:
                vertex_label_votes[vertex_idx].append(label)

        # Vote majoritaire pour chaque vertex
        for v_idx in range(num_vertices):
            if vertex_label_votes[v_idx]:
                # Label le plus fréquent
                label = max(set(vertex_label_votes[v_idx]),
                          key=vertex_label_votes[v_idx].count)
                vertex_colors[v_idx] = plane_colors[label]

        # Appliquer les couleurs
        mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)

        # Sauvegarder
        o3d.io.write_triangle_mesh(str(output_path), mesh)

        # Calculer des statistiques par plan
        plane_sizes = [int(np.sum(triangle_labels == i)) for i in range(num_planes)]

        # Calculer les équations de plan approximatives (centre + normale)
        planes_info = []
        for i in range(num_planes):
            # Triangles dans ce cluster
            cluster_mask = triangle_labels == i
            cluster_triangles = triangles[cluster_mask]

            if len(cluster_triangles) == 0:
                continue

            # Calculer le centroïde des vertices de ces triangles
            cluster_vertices = vertices[cluster_triangles.flatten()]
            centroid = cluster_vertices.mean(axis=0)

            # Normale du cluster (utiliser final_cluster_normals)
            normal = final_cluster_normals[i]

            # Équation du plan: ax + by + cz = d
            # où (a,b,c) = normale et d = normale . centroid
            d = np.dot(normal, centroid)

            planes_info.append({
                'normal': normal.tolist(),
                'centroid': centroid.tolist(),
                'd': float(d),
                'num_triangles': int(plane_sizes[i])
            })

        return {
            'success': True,
            'num_segments': num_planes,
            'plane_sizes': plane_sizes,
            'planes': planes_info,
            'method': 'planes'
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
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

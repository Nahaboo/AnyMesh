"""
Module de simplification de maillages 3D avec Open3D et Trimesh
"""

from pathlib import Path
from typing import Dict, Any, Tuple
import open3d as o3d
import trimesh
import numpy as np
import copy


def build_triangle_adjacency(triangles: np.ndarray) -> list:
    """
    Construit l'adjacence triangle-a-triangle via les aretes partagees.

    Args:
        triangles: Array numpy de shape (N, 3) avec les indices des triangles

    Returns:
        Liste de N sets, chaque set contient les indices des triangles voisins
    """
    edge_to_triangles = {}

    # Pour chaque triangle, enregistrer ses 3 aretes
    for tri_idx, tri in enumerate(triangles):
        edges = [
            tuple(sorted([tri[0], tri[1]])),
            tuple(sorted([tri[1], tri[2]])),
            tuple(sorted([tri[2], tri[0]]))
        ]
        for edge in edges:
            if edge not in edge_to_triangles:
                edge_to_triangles[edge] = []
            edge_to_triangles[edge].append(tri_idx)

    # Construire la liste d'adjacence
    tri_neighbors = [set() for _ in range(len(triangles))]
    for edge, tri_indices in edge_to_triangles.items():
        if len(tri_indices) == 2:
            tri_neighbors[tri_indices[0]].add(tri_indices[1])
            tri_neighbors[tri_indices[1]].add(tri_indices[0])

    return tri_neighbors


def compute_triangle_curvature(mesh: o3d.geometry.TriangleMesh) -> np.ndarray:
    """
    Calcule la courbure de chaque triangle via deviation des normales.

    Methode: Pour chaque triangle, compare sa normale avec celles de ses voisins.
    Deviation = 1 - moyenne(dot_products)
    - Valeur proche de 0.0 = zone plate (normales alignees)
    - Valeur proche de 1.0 = zone courbe (normales divergentes)

    Args:
        mesh: TriangleMesh Open3D avec normales calculees

    Returns:
        Array numpy de deviations (courbure) par triangle
    """
    # Calculer les normales de triangles si pas deja fait
    if not mesh.has_triangle_normals():
        mesh.compute_triangle_normals()

    triangles = np.asarray(mesh.triangles)
    tri_normals = np.asarray(mesh.triangle_normals)

    # Construire l'adjacence triangle-triangle
    tri_neighbors = build_triangle_adjacency(triangles)

    # Calculer la deviation pour chaque triangle
    deviations = np.zeros(len(tri_normals))

    for tri_idx, neighbors in enumerate(tri_neighbors):
        if len(neighbors) == 0:
            # Pas de voisins = triangle isole, deviation = 0 (deja initialise)
            continue

        normal = tri_normals[tri_idx]
        neighbor_normals = tri_normals[list(neighbors)]

        # Dot product avec tous les voisins
        dots = np.dot(neighbor_normals, normal)

        # Deviation = 1 - moyenne des dot products
        # Si dot=1 (normales alignees) -> deviation=0 (plat)
        # Si dot=-1 (normales opposees) -> deviation=2 (tres courbe)
        deviations[tri_idx] = 1.0 - np.mean(dots)

    return deviations


def segment_mesh_by_curvature(
    mesh: o3d.geometry.TriangleMesh,
    deviations: np.ndarray,
    threshold: float
) -> Tuple[o3d.geometry.TriangleMesh, o3d.geometry.TriangleMesh]:
    """
    Segmente un mesh en deux sous-meshes: zones plates et zones courbes.

    Args:
        mesh: TriangleMesh original
        deviations: Courbure par triangle (de compute_triangle_curvature)
        threshold: Seuil de separation (deviation < threshold = plat)

    Returns:
        Tuple (flat_mesh, curved_mesh)
    """
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)

    # Classifier les triangles
    flat_indices = np.where(deviations < threshold)[0]
    curved_indices = np.where(deviations >= threshold)[0]

    def create_submesh(tri_indices):
        """Cree un sous-mesh a partir d'indices de triangles"""
        if len(tri_indices) == 0:
            # Mesh vide si aucun triangle
            return o3d.geometry.TriangleMesh()

        submesh = o3d.geometry.TriangleMesh()
        submesh.vertices = o3d.utility.Vector3dVector(vertices)
        submesh.triangles = o3d.utility.Vector3iVector(triangles[tri_indices])

        # Supprimer les vertices non references
        submesh.remove_unreferenced_vertices()
        submesh.compute_vertex_normals()

        return submesh

    flat_mesh = create_submesh(flat_indices)
    curved_mesh = create_submesh(curved_indices)

    return flat_mesh, curved_mesh


def adaptive_simplify_mesh(
    input_path: Path,
    output_path: Path,
    target_ratio: float = 0.5,
    flat_multiplier: float = 2.0,
    curvature_threshold: float = None
) -> Dict[str, Any]:
    """
    Simplifie un maillage de maniere adaptative: zones plates simplifiees plus agressivement.

    NOUVELLE APPROCHE: Simplification progressive par couches au lieu de segmentation.
    Cela evite les trous crees par la separation et fusion des submeshes.

    Args:
        input_path: Chemin vers le fichier d'entree
        output_path: Chemin vers le fichier de sortie
        target_ratio: Ratio de reduction de base (0.0 - 1.0), ex: 0.5 = reduction de 50%
        flat_multiplier: Multiplicateur pour zones plates (ex: 2.0 = 2x plus agressif)
        curvature_threshold: Seuil de separation plat/courbe (None = auto)

    Returns:
        Dictionnaire contenant les statistiques de simplification
    """
    try:
        # Verification fichier
        if not input_path.exists():
            return {
                'success': False,
                'error': f"Le fichier d'entree n'existe pas: {input_path}"
            }

        # Chargement du mesh
        mesh_original = o3d.io.read_triangle_mesh(str(input_path))

        if not mesh_original.has_vertices() or len(mesh_original.vertices) == 0:
            return {
                'success': False,
                'error': "Le maillage ne contient pas de vertices valides"
            }

        original_vertices = len(mesh_original.vertices)
        original_triangles = len(mesh_original.triangles)

        # Etape 1: Calculer la courbure de chaque triangle
        deviations = compute_triangle_curvature(mesh_original)

        # Etape 2: Determiner le seuil automatiquement si non fourni
        if curvature_threshold is None:
            # Seuil = moyenne + 0.3 * ecart-type (valide empiriquement)
            curvature_threshold = np.mean(deviations) + 0.3 * np.std(deviations)

        # Etape 3: Classifier les triangles (pour stats uniquement)
        flat_mask = deviations < curvature_threshold
        flat_triangles_count = np.sum(flat_mask)
        curved_triangles_count = len(deviations) - flat_triangles_count

        # NOUVELLE APPROCHE: Simplification en une seule passe avec boundary_weight adaptatif
        #
        # Strategie: On utilise un boundary_weight faible pour permettre une simplification
        # plus agressive globalement. Le QEM va naturellement simplifier plus les zones plates
        # (faible cout d'erreur) que les zones courbes (cout d'erreur eleve).
        #
        # Le flat_multiplier influence la cible finale: plus il est eleve, plus on simplifie.

        # Calcul de la cible finale en fonction du ratio de zones plates
        flat_percentage = flat_triangles_count / original_triangles if original_triangles > 0 else 0

        # Si beaucoup de zones plates, on peut etre plus agressif
        # Formule: target_ratio de base + bonus proportionnel au % de plat * flat_multiplier
        effective_ratio = target_ratio + (flat_percentage * target_ratio * (flat_multiplier - 1.0) * 0.5)
        effective_ratio = min(0.95, effective_ratio)  # Cap a 95% de reduction max

        final_target = int(original_triangles * (1 - effective_ratio))
        final_target = max(4, final_target)  # Minimum 4 triangles (tetraedre)

        # Simplification en une passe avec boundary_weight modere
        mesh_final = mesh_original.simplify_quadric_decimation(
            target_number_of_triangles=final_target,
            maximum_error=float('inf'),
            boundary_weight=2.0  # Compromis: preserve un peu les bords sans trop bloquer
        )

        # Nettoyage final
        mesh_final.compute_vertex_normals()

        # Sauvegarde
        o3d.io.write_triangle_mesh(str(output_path), mesh_final)

        # Statistiques detaillees
        final_vertices = len(mesh_final.vertices)
        final_triangles = len(mesh_final.triangles)

        stats = {
            'success': True,
            'original_vertices': original_vertices,
            'original_triangles': original_triangles,
            'simplified_vertices': final_vertices,
            'simplified_triangles': final_triangles,
            'vertices_ratio': 1 - (final_vertices / original_vertices) if original_vertices > 0 else 0,
            'triangles_ratio': 1 - (final_triangles / original_triangles) if original_triangles > 0 else 0,
            'vertices_removed': original_vertices - final_vertices,
            'triangles_removed': original_triangles - final_triangles,
            'output_file': str(output_path),
            'output_size': output_path.stat().st_size,
            # Stats specifiques a la simplification adaptative
            'adaptive_stats': {
                'curvature_threshold': float(curvature_threshold),
                'flat_triangles_original': int(flat_triangles_count),
                'curved_triangles_original': int(curved_triangles_count),
                'flat_triangles_final': 0,  # Non applicable avec nouvelle approche
                'curved_triangles_final': 0,  # Non applicable avec nouvelle approche
                'effective_reduction_ratio': effective_ratio,
                'target_reduction_ratio': target_ratio,
                'flat_percentage': (flat_triangles_count / original_triangles * 100) if original_triangles > 0 else 0,
                'flat_multiplier': flat_multiplier,
                'method': 'single_pass_adaptive'
            }
        }

        return stats

    except Exception as e:
        return {
            'success': False,
            'error': f"Erreur lors de la simplification adaptative: {str(e)}"
        }


def simplify_mesh_trimesh(
    input_path: Path,
    output_path: Path,
    target_triangles: int = None,
    reduction_ratio: float = None,
    preserve_boundary: bool = True
) -> Dict[str, Any]:
    """
    Simplifie un maillage 3D avec Trimesh (ancienne implémentation).

    Utilise l'algorithme Quadric Error Metric de Trimesh.

    Args:
        input_path: Chemin vers le fichier d'entrée
        output_path: Chemin vers le fichier de sortie
        target_triangles: Nombre cible de triangles (prioritaire sur reduction_ratio)
        reduction_ratio: Ratio de réduction (0.0 - 1.0), ex: 0.5 = réduction de 50%
        preserve_boundary: Préserve les bords du maillage (non utilisé avec Trimesh)

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
        mesh_simplified = mesh_simplified.simplify_quadric_decimation(
            face_count=target_triangles
        )

        # Recalcul des normales
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
            'error': f"Erreur lors de la simplification Trimesh: {str(e)}"
        }


def simplify_mesh_glb(
    input_path: Path,
    output_path: Path,
    target_triangles: int = None,
    reduction_ratio: float = None
) -> Dict[str, Any]:
    """
    GLB-First: Simplifie un GLB directement avec Trimesh.

    Cette fonction est le coeur de la simplification GLB-First:
    - Charge le GLB directement (pas de conversion intermédiaire)
    - Simplifie avec Quadric Error Metric
    - Exporte en GLB

    ATTENTION: Les textures et matériaux sont perdus lors de la simplification
    car les UVs deviennent invalides après modification de la géométrie.

    Args:
        input_path: Chemin vers le fichier GLB d'entrée
        output_path: Chemin vers le fichier GLB de sortie
        target_triangles: Nombre cible de triangles (prioritaire)
        reduction_ratio: Ratio de réduction (0.0 - 1.0), ex: 0.5 = 50% de faces

    Returns:
        Dictionnaire contenant les statistiques de simplification
    """
    try:
        if not input_path.exists():
            return {
                'success': False,
                'error': f"Le fichier d'entree n'existe pas: {input_path}"
            }

        if target_triangles is None and reduction_ratio is None:
            return {
                'success': False,
                'error': "Vous devez specifier target_triangles ou reduction_ratio"
            }

        # Charger le GLB avec Trimesh
        loaded = trimesh.load(str(input_path))

        # Gérer les Scenes (plusieurs meshes dans un GLB)
        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                return {'success': False, 'error': 'Scene vide, aucune geometrie'}
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            return {'success': False, 'error': 'Pas de vertices valides'}
        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            return {'success': False, 'error': 'Pas de faces valides'}

        # Détecter si textures présentes (pour warning)
        had_textures = (
            hasattr(mesh, 'visual') and
            hasattr(mesh.visual, 'material') and
            mesh.visual.material is not None
        )

        original_vertices = len(mesh.vertices)
        original_triangles = len(mesh.faces)

        # Calcul du nombre cible
        if target_triangles is None:
            target_triangles = int(original_triangles * (1 - reduction_ratio))

        target_triangles = int(target_triangles)
        target_triangles = max(4, min(target_triangles, original_triangles))

        # Copie profonde pour simplification
        mesh_simplified = copy.deepcopy(mesh)

        # Simplification Quadric Error Metric
        mesh_simplified = mesh_simplified.simplify_quadric_decimation(
            face_count=target_triangles
        )

        # Exporter en GLB
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
            'textures_lost': had_textures  # Toujours perdues après simplification
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Erreur simplification GLB: {str(e)}"
        }


def simplify_mesh(
    input_path: Path,
    output_path: Path,
    target_triangles: int = None,
    reduction_ratio: float = None,
    preserve_boundary: bool = True,
    use_trimesh: bool = False
) -> Dict[str, Any]:
    """
    Simplifie un maillage 3D en réduisant le nombre de triangles.

    Utilise l'algorithme Quadric Error Metric (QEM).
    Peut utiliser Open3D (par défaut) ou Trimesh (si use_trimesh=True).

    Args:
        input_path: Chemin vers le fichier d'entrée
        output_path: Chemin vers le fichier de sortie
        target_triangles: Nombre cible de triangles (prioritaire sur reduction_ratio)
        reduction_ratio: Ratio de réduction (0.0 - 1.0), ex: 0.5 = réduction de 50%
        preserve_boundary: Préserve les bords du maillage (boundary_weight=3.0 si True, Open3D seulement)
        use_trimesh: Si True, utilise Trimesh au lieu d'Open3D

    Returns:
        Dictionnaire contenant les statistiques de simplification ou erreur
    """
    # Rediriger vers Trimesh si demandé
    if use_trimesh:
        return simplify_mesh_trimesh(
            input_path=input_path,
            output_path=output_path,
            target_triangles=target_triangles,
            reduction_ratio=reduction_ratio,
            preserve_boundary=preserve_boundary
        )

    # Sinon, utiliser Open3D (comportement par défaut)
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

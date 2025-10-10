"""
Script de test pour vérifier l'installation d'Open3D
et tester la simplification de maillage
"""

import open3d as o3d
import numpy as np

def test_open3d_installation():
    """Vérifie que Open3D est correctement installé"""
    print(f"Open3D version: {o3d.__version__}")
    print("[OK] Open3D est correctement installe\n")

def create_test_mesh():
    """Crée un maillage de test (une sphère)"""
    print("Création d'un maillage de test (sphère)...")
    mesh = o3d.geometry.TriangleMesh.create_sphere(radius=1.0, resolution=20)
    mesh.compute_vertex_normals()

    print(f"  Nombre de vertices: {len(mesh.vertices)}")
    print(f"  Nombre de triangles: {len(mesh.triangles)}")
    print("[OK] Maillage cree\n")

    return mesh

def simplify_mesh(mesh, target_triangles):
    """Simplifie le maillage"""
    print(f"Simplification du maillage (cible: {target_triangles} triangles)...")

    simplified_mesh = mesh.simplify_quadric_decimation(
        target_number_of_triangles=target_triangles
    )

    print(f"  Vertices apres simplification: {len(simplified_mesh.vertices)}")
    print(f"  Triangles apres simplification: {len(simplified_mesh.triangles)}")
    print("[OK] Simplification reussie\n")

    return simplified_mesh

def visualize_meshes(original_mesh, simplified_mesh):
    """Visualise les deux maillages côte à côte"""
    print("Lancement de la visualisation...")
    print("  Maillage gauche: Original")
    print("  Maillage droit: Simplifié")

    # Positionner les maillages côte à côte
    original_mesh.translate([-1.5, 0, 0])
    simplified_mesh.translate([1.5, 0, 0])

    # Colorer différemment
    original_mesh.paint_uniform_color([0.7, 0.7, 0.7])
    simplified_mesh.paint_uniform_color([0.3, 0.7, 0.9])

    o3d.visualization.draw_geometries(
        [original_mesh, simplified_mesh],
        window_name="Test Open3D - Original (gauche) vs Simplifié (droit)",
        width=1200,
        height=800
    )

def main():
    print("=" * 50)
    print("Test de l'environnement Open3D")
    print("=" * 50 + "\n")

    # Test de l'installation
    test_open3d_installation()

    # Créer un maillage de test
    mesh = create_test_mesh()

    # Dupliquer pour garder l'original intact
    import copy
    mesh_copy = copy.deepcopy(mesh)

    # Simplifier le maillage (réduire à 50% des triangles)
    original_triangles = len(mesh.triangles)
    target_triangles = original_triangles // 2
    simplified_mesh = simplify_mesh(mesh_copy, target_triangles)

    # Calculer le taux de réduction
    reduction_rate = (1 - len(simplified_mesh.triangles) / original_triangles) * 100
    print(f"Taux de réduction: {reduction_rate:.1f}%\n")

    # Visualiser
    visualize_meshes(mesh, simplified_mesh)

    print("[OK] Test termine avec succes!")

if __name__ == "__main__":
    main()

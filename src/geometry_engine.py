import pyvista as pv
import trimesh
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def to_pyvista(input_path: Path) -> pv.PolyData:
    """
    Charge n'importe quel format 3D (GLB, OBJ, STL, PLY...) via Trimesh
    et retourne un objet PyVista PolyData prêt pour le pipeline VTK.
    """
    loaded = trimesh.load(str(input_path))
    if isinstance(loaded, trimesh.Scene):
        meshes = list(loaded.geometry.values())
        if len(meshes) == 0:
            raise ValueError(f"Scene vide, aucune geometrie: {input_path.name}")
        mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
    else:
        mesh = loaded

    if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
        raise ValueError(f"Pas de faces valides: {input_path.name}")

    # Conversion Trimesh -> PyVista (format VTK: [3, v0, v1, v2, ...])
    faces_vtk = np.column_stack([
        np.full(len(mesh.faces), 3),
        mesh.faces
    ]).flatten()

    return pv.PolyData(np.array(mesh.vertices), faces_vtk)


class MeshSanitizer:
    """
    Moteur de reconstruction géométrique pour transformer les sorties IA 
    en maillages industriels (Manifold/Watertight).
    """
    
    def __init__(self, voxel_resolution: int = 256):
        self.voxel_resolution = voxel_resolution

    def sample_mesh_to_cloud(self, mesh: trimesh.Trimesh, num_points: int = 50000) -> pv.PolyData:
        """
        Étape 1 : Échantillonnage. On oublie la topologie initiale pour 
        ne garder que la 'forme' sous forme de nuage de points.
        """
        points = mesh.sample(num_points)
        # Conversion vers le format PyVista/VTK
        cloud = pv.PolyData(points)
        return cloud

    def reconstruct_surface(self, cloud: pv.PolyData) -> pv.PolyData:
        """
        Étape 2 : Reconstruction via SDF/Voxel.
        Génère une surface parfaitement fermée (watertight).
        reconstruct_surface estime les normales en interne via nbr_sz.
        """
        surface = cloud.reconstruct_surface(nbr_sz=20, sample_spacing=None)
        return surface

    def finalize_manifold(self, pv_mesh: pv.PolyData) -> trimesh.Trimesh:
        """
        Étape 3 : Réparation ultime. Suppression des faces dégénérées
        et garantie de l'intégrité manifold.
        """
        import pymeshfix as mf
        
        meshfix = mf.MeshFix(pv_mesh)
        meshfix.repair() # Remplissage des trous restants et correction des normales
        
        # Retour vers Trimesh pour la compatibilité avec le reste de l'app
        fixed_mesh = trimesh.Trimesh(
            vertices=meshfix.v, 
            faces=meshfix.f, 
            process=True
        )
        return fixed_mesh

    def sanitize_pipeline(self, input_path: Path, output_path: Path) -> Dict[str, Any]:
        """
        Pipeline complet : Mesh IA -> Points -> Clean Mesh
        """
        try:
            # Chargement
            mesh_raw = trimesh.load(str(input_path))
            if isinstance(mesh_raw, trimesh.Scene):
                mesh_raw = mesh_raw.dump(concatenate=True)

            logger.info(f"Sanitizing mesh: {input_path.name}")
            
            # Workflow
            cloud = self.sample_mesh_to_cloud(mesh_raw)
            surface = self.reconstruct_surface(cloud)
            final_mesh = self.finalize_manifold(surface)
            
            # Export
            final_mesh.export(str(output_path))
            
            return {
                "success": True,
                "is_watertight": final_mesh.is_watertight,
                "vertices": len(final_mesh.vertices),
                "faces": len(final_mesh.faces)
            }
        except Exception as e:
            logger.error(f"Sanitization failed: {str(e)}")
            return {"success": False, "error": str(e)}
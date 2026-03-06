import pyvista as pv
import trimesh
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def to_pyvista(input_path: Path) -> pv.PolyData:
    """Load any 3D format via Trimesh and return a PyVista PolyData object."""
    loaded = trimesh.load(str(input_path))
    if isinstance(loaded, trimesh.Scene):
        meshes = list(loaded.geometry.values())
        if len(meshes) == 0:
            raise ValueError(f"Empty scene, no geometry: {input_path.name}")
        mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
    else:
        mesh = loaded

    if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
        raise ValueError(f"No valid faces: {input_path.name}")

    # VTK face format: [3, v0, v1, v2, ...]
    faces_vtk = np.column_stack([
        np.full(len(mesh.faces), 3),
        mesh.faces
    ]).flatten()

    return pv.PolyData(np.array(mesh.vertices), faces_vtk)


class MeshSanitizer:
    """Geometric reconstruction pipeline. Converts AI mesh output to manifold/watertight geometry."""
    
    def __init__(self, voxel_resolution: int = 256):
        self.voxel_resolution = voxel_resolution

    def sample_mesh_to_cloud(self, mesh: trimesh.Trimesh, num_points: int = 50000) -> pv.PolyData:
        """Step 1: Sample the mesh surface into a point cloud, discarding original topology."""
        points = mesh.sample(num_points)
        cloud = pv.PolyData(points)
        return cloud

    def reconstruct_surface(self, cloud: pv.PolyData) -> pv.PolyData:
        """Step 2: Reconstruct a closed watertight surface from the point cloud."""
        surface = cloud.reconstruct_surface(nbr_sz=20, sample_spacing=None)
        return surface

    def finalize_manifold(self, pv_mesh: pv.PolyData) -> trimesh.Trimesh:
        """Step 3: Fill remaining holes and fix normals using pymeshfix."""
        import pymeshfix as mf

        meshfix = mf.MeshFix(pv_mesh)
        meshfix.repair()

        fixed_mesh = trimesh.Trimesh(
            vertices=meshfix.points,
            faces=meshfix.faces,
            process=True
        )
        return fixed_mesh

    def sanitize_pipeline(self, input_path: Path, output_path: Path) -> Dict[str, Any]:
        """Full pipeline: AI mesh -> point cloud -> clean watertight mesh."""
        try:
            mesh_raw = trimesh.load(str(input_path))
            if isinstance(mesh_raw, trimesh.Scene):
                mesh_raw = mesh_raw.dump(concatenate=True)

            logger.info(f"Sanitizing mesh: {input_path.name}")

            cloud = self.sample_mesh_to_cloud(mesh_raw)
            surface = self.reconstruct_surface(cloud)
            final_mesh = self.finalize_manifold(surface)

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
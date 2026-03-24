import pyvista as pv
import trimesh
import numpy as np
from pathlib import Path
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



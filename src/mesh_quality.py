"""
Mesh Quality Diagnostics — MeshLab-style surface quality analysis.
Computes boundary edges, non-manifold edges/vertices, degenerate faces.
Returns edge positions for frontend LineSegments overlay.
"""
import logging
import numpy as np
import trimesh
from pathlib import Path

logger = logging.getLogger(__name__)


def compute_quality_stats(mesh_path: Path) -> dict:
    """Compute mesh quality statistics + edge positions for overlays."""
    try:
        mesh = trimesh.load(str(mesh_path), force='mesh')
    except Exception as e:
        return {"success": False, "error": f"Failed to load mesh: {e}"}

    n_verts = len(mesh.vertices)
    n_faces = len(mesh.faces)
    vertices = mesh.vertices

    # --- Edge analysis via numpy (evite Counter + tuples python) ---
    edges = mesh.edges_sorted  # (n_edges, 2)
    # Encoder chaque edge comme un entier unique pour np.unique
    max_idx = n_verts
    edge_keys = edges[:, 0] * max_idx + edges[:, 1]
    unique_keys, inverse, counts = np.unique(edge_keys, return_inverse=True, return_counts=True)

    # Decoder les unique keys en paires de vertex indices
    unique_edges = np.stack([unique_keys // max_idx, unique_keys % max_idx], axis=1)

    # Boundary edges: apparaissent dans exactement 1 face
    boundary_mask = counts == 1
    boundary_edges = unique_edges[boundary_mask]
    boundary_edges_count = int(boundary_mask.sum())

    # Non-manifold edges: apparaissent dans >2 faces
    non_manifold_mask = counts > 2
    non_manifold_edges = unique_edges[non_manifold_mask]
    non_manifold_edges_count = int(non_manifold_mask.sum())

    # Boundary vertices
    boundary_verts = np.unique(boundary_edges.ravel()) if boundary_edges_count > 0 else np.array([], dtype=int)

    # Non-manifold vertices
    non_manifold_verts = np.unique(non_manifold_edges.ravel()) if non_manifold_edges_count > 0 else np.array([], dtype=int)

    # Boundary faces: faces qui ont au moins une boundary edge
    # Reconstruire un set de keys boundary pour lookup rapide
    boundary_key_set = set(unique_keys[boundary_mask].tolist())
    face_edge_keys = np.stack([
        mesh.faces[:, 0] * max_idx + mesh.faces[:, 1],
        mesh.faces[:, 1] * max_idx + mesh.faces[:, 2],
        mesh.faces[:, 2] * max_idx + mesh.faces[:, 0],
    ], axis=1)
    # Aussi les edges inverses (edges_sorted = toujours [min, max])
    face_edges_sorted = np.sort(mesh.faces.reshape(-1, 1) * np.ones((1, 3), dtype=int), axis=0)
    # Approche simple : compter les faces dont au moins une edge est boundary
    f0 = np.minimum(mesh.faces[:, 0], mesh.faces[:, 1]) * max_idx + np.maximum(mesh.faces[:, 0], mesh.faces[:, 1])
    f1 = np.minimum(mesh.faces[:, 1], mesh.faces[:, 2]) * max_idx + np.maximum(mesh.faces[:, 1], mesh.faces[:, 2])
    f2 = np.minimum(mesh.faces[:, 2], mesh.faces[:, 0]) * max_idx + np.maximum(mesh.faces[:, 2], mesh.faces[:, 0])
    boundary_faces_mask = (
        np.isin(f0, list(boundary_key_set)) |
        np.isin(f1, list(boundary_key_set)) |
        np.isin(f2, list(boundary_key_set))
    )
    boundary_faces_count = int(boundary_faces_mask.sum())

    # --- Edge positions pour le frontend overlay (flat arrays numpy -> list) ---
    boundary_edge_positions = []
    if boundary_edges_count > 0:
        v0 = vertices[boundary_edges[:, 0]]
        v1 = vertices[boundary_edges[:, 1]]
        boundary_edge_positions = np.hstack([v0, v1]).ravel().tolist()

    non_manifold_edge_positions = []
    if non_manifold_edges_count > 0:
        v0 = vertices[non_manifold_edges[:, 0]]
        v1 = vertices[non_manifold_edges[:, 1]]
        non_manifold_edge_positions = np.hstack([v0, v1]).ravel().tolist()

    # --- Degenerate faces (min angle < 1 degree) ---
    min_angles_deg = np.degrees(np.min(mesh.face_angles, axis=1))
    degenerate_faces_count = int(np.sum(min_angles_deg < 1.0))

    logger.info(f"[QUALITY] {n_verts}v/{n_faces}f | "
                f"Boundary: {boundary_edges_count}e/{boundary_faces_count}f | "
                f"Non-manifold: {non_manifold_edges_count}e/{len(non_manifold_verts)}v | "
                f"Degenerate: {degenerate_faces_count}f")

    return {
        "success": True,
        "vertices_count": n_verts,
        "faces_count": n_faces,
        "boundary_edges": boundary_edges_count,
        "boundary_faces": boundary_faces_count,
        "boundary_vertices": len(boundary_verts),
        "non_manifold_edges": non_manifold_edges_count,
        "non_manifold_vertices": len(non_manifold_verts),
        "degenerate_faces": degenerate_faces_count,
        "is_watertight": bool(mesh.is_watertight),
        "is_winding_consistent": bool(mesh.is_winding_consistent),
        # Edge positions for frontend LineSegments overlay
        "boundary_edge_positions": boundary_edge_positions,
        "non_manifold_edge_positions": non_manifold_edge_positions,
    }

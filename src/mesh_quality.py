"""
Mesh Quality Diagnostics — MeshLab-style surface quality analysis.
Computes boundary edges, non-manifold edges/vertices, face quality stats.
Returns edge positions for frontend LineSegments overlay.
Can generate vertex-colored GLB for face quality heatmap.
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

    # --- Face quality (min angle per face) ---
    face_angles = mesh.face_angles  # (n_faces, 3) in radians
    min_angles_deg = np.degrees(np.min(face_angles, axis=1))
    degenerate_threshold = 1.0  # degrees
    degenerate_faces_count = int(np.sum(min_angles_deg < degenerate_threshold))

    avg_min_angle = float(np.mean(min_angles_deg))
    worst_min_angle = float(np.min(min_angles_deg))

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
        "euler_number": int(mesh.euler_number),
        "avg_min_angle": round(avg_min_angle, 2),
        "worst_min_angle": round(worst_min_angle, 2),
        # Edge positions for frontend LineSegments overlay
        "boundary_edge_positions": boundary_edge_positions,
        "non_manifold_edge_positions": non_manifold_edge_positions,
    }


def generate_quality_visualization(mesh_path: Path, output_path: Path, diagnostic_type: str) -> dict:
    """Generate a vertex-colored GLB for face quality heatmap."""
    try:
        mesh = trimesh.load(str(mesh_path), force='mesh')
    except Exception as e:
        return {"success": False, "error": f"Failed to load mesh: {e}"}

    n_verts = len(mesh.vertices)

    if diagnostic_type == "face_quality":
        vertex_colors = _highlight_face_quality(mesh, n_verts)
    else:
        return {"success": False, "error": f"Only face_quality uses GLB visualization"}

    colored_mesh = trimesh.Trimesh(
        vertices=mesh.vertices,
        faces=mesh.faces,
        vertex_colors=vertex_colors,
        process=False
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    colored_mesh.export(str(output_path), file_type='glb')

    logger.info(f"[QUALITY] Face quality heatmap saved: {output_path.name}")

    return {
        "success": True,
        "output_file": str(output_path),
        "output_filename": output_path.name,
        "diagnostic_type": diagnostic_type,
        "total_vertices": n_verts,
    }


def _highlight_face_quality(mesh, n_verts: int) -> np.ndarray:
    """Heatmap based on min angle per vertex (blue=good, red=bad).
    Normalized relative to the mesh's own min/max range for maximum contrast."""
    face_angles = mesh.face_angles  # (n_faces, 3) radians
    min_angles = np.min(face_angles, axis=1)  # worst angle per face

    vertex_quality = np.full(n_verts, np.pi / 3)  # default = 60deg (perfect)
    np.minimum.at(vertex_quality, mesh.faces[:, 0], min_angles)
    np.minimum.at(vertex_quality, mesh.faces[:, 1], min_angles)
    np.minimum.at(vertex_quality, mesh.faces[:, 2], min_angles)

    # Normalize relative to mesh's own range for maximum color contrast
    q_min = vertex_quality.min()
    q_max = vertex_quality.max()
    if q_max > q_min:
        quality_normalized = 1.0 - (vertex_quality - q_min) / (q_max - q_min)
    else:
        quality_normalized = np.zeros(n_verts)

    return _heatmap_colors(quality_normalized)


def _heatmap_colors(values: np.ndarray) -> np.ndarray:
    """Map [0,1] values to Blue->Cyan->Green->Yellow->Red heatmap."""
    d = np.clip(values, 0.0, 1.0)
    n = len(d)
    colors = np.ones((n, 4), dtype=np.uint8)
    colors[:, 3] = 255

    r = np.zeros(n)
    g = np.zeros(n)
    b = np.zeros(n)

    mask = d < 0.25
    f = d[mask] / 0.25
    r[mask] = 0; g[mask] = f; b[mask] = 1.0

    mask = (d >= 0.25) & (d < 0.5)
    f = (d[mask] - 0.25) / 0.25
    r[mask] = 0; g[mask] = 1.0; b[mask] = 1.0 - f

    mask = (d >= 0.5) & (d < 0.75)
    f = (d[mask] - 0.5) / 0.25
    r[mask] = f; g[mask] = 1.0; b[mask] = 0

    mask = d >= 0.75
    f = (d[mask] - 0.75) / 0.25
    r[mask] = 1.0; g[mask] = 1.0 - f; b[mask] = 0

    colors[:, 0] = (r * 255).astype(np.uint8)
    colors[:, 1] = (g * 255).astype(np.uint8)
    colors[:, 2] = (b * 255).astype(np.uint8)

    return colors

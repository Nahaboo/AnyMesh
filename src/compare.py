"""
Mesh Comparison — compute distance between two meshes and generate heatmap.
Uses scipy KDTree for robust vertex-to-surface distance computation.
Output: GLB with vertex colors (heatmap) + distance statistics.
"""
import logging
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from pathlib import Path

logger = logging.getLogger(__name__)


def _distance_to_color(distances: np.ndarray) -> np.ndarray:
    """Map normalized distances [0,1] to RGBA heatmap colors (vectorized).

    Blue(0%) -> Cyan(25%) -> Green(50%) -> Yellow(75%) -> Red(100%)
    """
    d = np.clip(distances, 0.0, 1.0)
    n = len(d)
    colors = np.ones((n, 4), dtype=np.uint8)
    colors[:, 3] = 255

    # Vectorized color mapping
    r = np.zeros(n)
    g = np.zeros(n)
    b = np.zeros(n)

    # Blue -> Cyan (0 - 0.25)
    mask = d < 0.25
    f = d[mask] / 0.25
    r[mask] = 0; g[mask] = f; b[mask] = 1.0

    # Cyan -> Green (0.25 - 0.5)
    mask = (d >= 0.25) & (d < 0.5)
    f = (d[mask] - 0.25) / 0.25
    r[mask] = 0; g[mask] = 1.0; b[mask] = 1.0 - f

    # Green -> Yellow (0.5 - 0.75)
    mask = (d >= 0.5) & (d < 0.75)
    f = (d[mask] - 0.5) / 0.25
    r[mask] = f; g[mask] = 1.0; b[mask] = 0

    # Yellow -> Red (0.75 - 1.0)
    mask = d >= 0.75
    f = (d[mask] - 0.75) / 0.25
    r[mask] = 1.0; g[mask] = 1.0 - f; b[mask] = 0

    colors[:, 0] = (r * 255).astype(np.uint8)
    colors[:, 1] = (g * 255).astype(np.uint8)
    colors[:, 2] = (b * 255).astype(np.uint8)

    return colors


def compare_meshes(mesh_ref_path: Path, mesh_comp_path: Path, output_path: Path) -> dict:
    """Compare two meshes and generate a heatmap GLB.

    Uses dense point sampling on the reference mesh surface + KDTree
    for accurate point-to-surface distance computation.
    """
    try:
        mesh_ref = trimesh.load(str(mesh_ref_path), force='mesh')
        mesh_comp = trimesh.load(str(mesh_comp_path), force='mesh')
    except Exception as e:
        return {"success": False, "error": f"Failed to load meshes: {e}"}

    # Clean degenerate faces that cause issues
    mesh_ref.remove_degenerate_faces()
    mesh_comp.remove_degenerate_faces()

    logger.info(f"[COMPARE] Ref: {len(mesh_ref.vertices)}v/{len(mesh_ref.faces)}f | "
                f"Comp: {len(mesh_comp.vertices)}v/{len(mesh_comp.faces)}f")

    # Sample dense points on the reference mesh surface for accurate distance
    # More samples = more accurate, 100k is a good balance
    num_samples = max(100000, len(mesh_ref.vertices) * 3)
    ref_surface_points = mesh_ref.sample(num_samples)
    logger.info(f"[COMPARE] Sampled {num_samples} points on reference surface")

    # Build KDTree from reference surface points
    tree = cKDTree(ref_surface_points)

    # For each vertex of the comparison mesh, find nearest surface point
    distances, _ = tree.query(mesh_comp.vertices)

    logger.info(f"[COMPARE] Distances: min={distances.min():.8f}, max={distances.max():.8f}, mean={distances.mean():.8f}")

    # Normalize by bounding box diagonal of reference mesh
    bb_diagonal = np.linalg.norm(mesh_ref.bounding_box.extents)
    if bb_diagonal < 1e-10:
        bb_diagonal = 1.0

    distances_normalized = distances / bb_diagonal

    # Stats
    hausdorff = float(np.max(distances))
    mean_dist = float(np.mean(distances))
    rms_dist = float(np.sqrt(np.mean(distances ** 2)))
    p95_dist = float(np.percentile(distances, 95))

    hausdorff_pct = float(np.max(distances_normalized) * 100)
    mean_pct = float(np.mean(distances_normalized) * 100)

    logger.info(f"[COMPARE] Hausdorff={hausdorff:.6f} ({hausdorff_pct:.2f}%), "
                f"Mean={mean_dist:.6f} ({mean_pct:.2f}%), RMS={rms_dist:.6f}, P95={p95_dist:.6f}")

    # Generate heatmap colors
    # Cap at 95th percentile for better contrast
    cap = p95_dist if p95_dist > 1e-10 else bb_diagonal * 0.01
    distances_for_color = np.clip(distances / cap, 0.0, 1.0)
    vertex_colors = _distance_to_color(distances_for_color)

    # Create output mesh with vertex colors
    heatmap_mesh = trimesh.Trimesh(
        vertices=mesh_comp.vertices,
        faces=mesh_comp.faces,
        vertex_colors=vertex_colors,
        process=False
    )

    # Save as GLB
    output_path.parent.mkdir(parents=True, exist_ok=True)
    heatmap_mesh.export(str(output_path), file_type='glb')

    logger.info(f"[COMPARE] Heatmap saved: {output_path.name}")

    return {
        "success": True,
        "output_file": str(output_path),
        "output_filename": output_path.name,
        "vertices_count": len(mesh_comp.vertices),
        "faces_count": len(mesh_comp.faces),
        "stats": {
            "hausdorff": round(hausdorff, 6),
            "hausdorff_pct": round(hausdorff_pct, 2),
            "mean": round(mean_dist, 6),
            "mean_pct": round(mean_pct, 2),
            "rms": round(rms_dist, 6),
            "p95": round(p95_dist, 6),
            "bb_diagonal": round(float(bb_diagonal), 6),
        },
        "ref_vertices": len(mesh_ref.vertices),
        "ref_faces": len(mesh_ref.faces),
        "comp_vertices": len(mesh_comp.vertices),
        "comp_faces": len(mesh_comp.faces),
    }

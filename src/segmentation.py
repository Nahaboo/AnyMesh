"""
3D mesh segmentation using Open3D and PyMeshLab.
"""

import open3d as o3d
import pymeshlab as ml
import numpy as np
import trimesh
from pathlib import Path
from typing import Dict, Any

from .temp_utils import get_temp_path, safe_delete


def segment_by_connectivity(
    input_path: Path,
    output_path: Path
) -> Dict[str, Any]:
    """
    Segment the mesh by connected components.

    Use case: detached handles, removable parts.
    Speed: very fast (< 1s).
    """
    try:
        mesh = o3d.io.read_triangle_mesh(str(input_path))

        if not mesh.has_vertices():
            return {'success': False, 'error': 'Empty mesh'}

        triangle_clusters, cluster_n_triangles, cluster_area = \
            mesh.cluster_connected_triangles()

        triangle_clusters = np.asarray(triangle_clusters)
        num_segments = triangle_clusters.max() + 1

        colors = np.random.rand(num_segments, 3)
        vertex_colors = np.zeros((len(mesh.vertices), 3))

        for tri_idx, cluster_id in enumerate(triangle_clusters):
            triangle = mesh.triangles[tri_idx]
            for vertex_idx in triangle:
                vertex_colors[vertex_idx] = colors[cluster_id]

        mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)
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
    Segment the mesh by detecting sharp edges.

    Use case: zippers, buckles, sewn borders.
    Speed: fast (1-3s).
    angle_threshold: minimum angle in degrees to classify an edge as sharp.
    """
    try:
        # Charger avec Open3D
        mesh = o3d.io.read_triangle_mesh(str(input_path))

        if not mesh.has_vertices():
            return {'success': False, 'error': 'Empty mesh'}

        mesh.compute_triangle_normals()

        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles)
        triangle_normals = np.asarray(mesh.triangle_normals)

        num_vertices = len(vertices)
        num_triangles = len(triangles)

        threshold_rad = np.radians(angle_threshold)

        print(f"  [SHARP_EDGES] Detecting sharp edges, threshold: {angle_threshold} deg")
        print(f"  Mesh: {num_vertices} vertices, {num_triangles} triangles")

        # edge_dict[edge] = [triangle_indices]
        edge_dict = {}

        for tri_idx, triangle in enumerate(triangles):
            edges = [
                tuple(sorted([triangle[0], triangle[1]])),
                tuple(sorted([triangle[1], triangle[2]])),
                tuple(sorted([triangle[2], triangle[0]]))
            ]

            for edge in edges:
                if edge not in edge_dict:
                    edge_dict[edge] = []
                edge_dict[edge].append(tri_idx)

        sharp_edges = set()

        for edge, tri_indices in edge_dict.items():
            if len(tri_indices) == 1:
                # Boundary edge: always sharp
                sharp_edges.add(edge)
            elif len(tri_indices) == 2:
                n1 = triangle_normals[tri_indices[0]]
                n2 = triangle_normals[tri_indices[1]]
                cos_angle = np.clip(np.dot(n1, n2), -1.0, 1.0)
                if np.arccos(cos_angle) > threshold_rad:
                    sharp_edges.add(edge)

        print(f"  [SHARP_EDGES] Detected {len(sharp_edges)} sharp edges")

        from scipy.sparse import lil_matrix
        from scipy.sparse.csgraph import connected_components

        # Build triangle adjacency graph, excluding sharp edges
        adjacency = lil_matrix((num_triangles, num_triangles), dtype=bool)

        for edge, tri_indices in edge_dict.items():
            if edge not in sharp_edges and len(tri_indices) == 2:
                adjacency[tri_indices[0], tri_indices[1]] = True
                adjacency[tri_indices[1], tri_indices[0]] = True

        num_segments, triangle_labels = connected_components(adjacency, directed=False)

        print(f"  [SHARP_EDGES] Segmented into {num_segments} regions")

        segment_colors = np.random.rand(num_segments, 3)

        # Assign vertex colors by majority vote from adjacent triangles
        vertex_colors = np.zeros((num_vertices, 3))
        vertex_segment_votes = [[] for _ in range(num_vertices)]

        for tri_idx, triangle in enumerate(triangles):
            segment_id = triangle_labels[tri_idx]
            for vertex_idx in triangle:
                vertex_segment_votes[vertex_idx].append(segment_id)

        for v_idx in range(num_vertices):
            if vertex_segment_votes[v_idx]:
                segment_id = max(set(vertex_segment_votes[v_idx]),
                               key=vertex_segment_votes[v_idx].count)
                vertex_colors[v_idx] = segment_colors[segment_id]

        mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)
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
    Segment the mesh by similar curvature zones using k-means.

    Curvature is approximated by the variance of adjacent triangle normals.
    Use case: flat vs rounded areas.
    Speed: moderate (3-10s depending on mesh size).
    """
    try:
        from sklearn.cluster import KMeans

        mesh = o3d.io.read_triangle_mesh(str(input_path))

        if not mesh.has_vertices():
            return {'success': False, 'error': 'Empty mesh'}

        if not mesh.has_vertex_normals():
            mesh.compute_vertex_normals()

        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles)
        vertex_normals = np.asarray(mesh.vertex_normals)

        num_vertices = len(vertices)

        print(f"  [CURVATURE] Computing curvature for {num_vertices} vertices")

        # vertex -> adjacent triangle indices
        vertex_to_triangles = [[] for _ in range(num_vertices)]
        for tri_idx, triangle in enumerate(triangles):
            for vertex_idx in triangle:
                vertex_to_triangles[vertex_idx].append(tri_idx)

        # Curvature = variance of angles between vertex normal and adjacent triangle normals
        curvatures = np.zeros(num_vertices)

        for v_idx in range(num_vertices):
            adjacent_tris = vertex_to_triangles[v_idx]

            if len(adjacent_tris) < 2:
                # Isolated vertex or boundary -> zero curvature
                curvatures[v_idx] = 0.0
                continue

            vertex_normal = vertex_normals[v_idx]
            angles = []
            for tri_idx in adjacent_tris:
                tri_verts = triangles[tri_idx]
                v0, v1, v2 = vertices[tri_verts[0]], vertices[tri_verts[1]], vertices[tri_verts[2]]
                edge1 = v1 - v0
                edge2 = v2 - v0
                tri_normal = np.cross(edge1, edge2)
                norm = np.linalg.norm(tri_normal)
                if norm > 0:
                    tri_normal = tri_normal / norm
                    cos_angle = np.clip(np.dot(vertex_normal, tri_normal), -1.0, 1.0)
                    angles.append(np.arccos(cos_angle))

            if len(angles) > 0:
                curvatures[v_idx] = np.var(angles)

        print(f"  [CURVATURE] Curvature min: {curvatures.min():.4f}, max: {curvatures.max():.4f}")

        curvature_mean = curvatures.mean()
        curvature_std = curvatures.std()

        if curvature_std > 0:
            curvatures_normalized = (curvatures - curvature_mean) / curvature_std
        else:
            curvatures_normalized = curvatures - curvature_mean

        X = curvatures_normalized.reshape(-1, 1)

        kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
        vertex_labels = kmeans.fit_predict(X)

        print(f"  [CURVATURE] K-means: {num_clusters} clusters")

        cluster_colors = np.random.rand(num_clusters, 3)
        vertex_colors = cluster_colors[vertex_labels]

        mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)
        o3d.io.write_triangle_mesh(str(output_path), mesh)

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
    Segment the mesh by detecting planar surfaces via normal clustering.

    Strategy: cluster triangles by similar normal direction, filter by coplanarity.
    Use case: watch faces, box sides.
    Speed: fast (1-3s).
    """
    try:
        from sklearn.cluster import KMeans

        mesh = o3d.io.read_triangle_mesh(str(input_path))

        if not mesh.has_vertices():
            return {'success': False, 'error': 'Empty mesh'}

        mesh.compute_triangle_normals()

        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles)
        triangle_normals = np.asarray(mesh.triangle_normals)

        num_vertices = len(vertices)
        num_triangles = len(triangles)

        print(f"  [PLANES] Detecting {num_planes} planes in {num_triangles} triangles")

        # Over-cluster first, then filter by planarity
        initial_clusters = max(num_planes * 2, 10)
        kmeans = KMeans(n_clusters=initial_clusters, random_state=42, n_init=10)
        triangle_labels_initial = kmeans.fit_predict(triangle_normals)

        print(f"  [PLANES] Initial k-means: {initial_clusters} groups")

        plane_clusters = []
        cluster_scores = []  # (cluster_id, variance, size)

        for cluster_id in range(initial_clusters):
            cluster_mask = triangle_labels_initial == cluster_id
            cluster_normals = triangle_normals[cluster_mask]
            cluster_size = len(cluster_normals)

            if cluster_size < 10:
                continue

            # Low normal variance = flat surface
            normal_variance = np.var(cluster_normals, axis=0).sum()
            cluster_scores.append((cluster_id, normal_variance, cluster_size))

        cluster_scores.sort(key=lambda x: x[1])

        if len(cluster_scores) > 0:
            variances = [score[1] for score in cluster_scores]
            # Adaptive threshold: median variance / 2, minimum 0.005
            adaptive_threshold = max(0.005, np.median(variances) / 2)
            print(f"  [PLANES] Planarity threshold: {adaptive_threshold:.6f}")

            for cluster_id, variance, size in cluster_scores:
                if variance < adaptive_threshold:
                    plane_clusters.append(cluster_id)

        print(f"  [PLANES] Found {len(plane_clusters)} truly planar surfaces")

        if len(plane_clusters) == 0:
            print(f"  [PLANES] No planar surface detected, falling back to plain clustering")
            triangle_labels = triangle_labels_initial
            num_planes = initial_clusters
        else:
            # 0 = non-planar, 1..N = detected planes
            triangle_labels = np.zeros(num_triangles, dtype=int)

            for new_id, old_cluster_id in enumerate(plane_clusters[:num_planes], start=1):
                cluster_mask = triangle_labels_initial == old_cluster_id
                triangle_labels[cluster_mask] = new_id

            num_planes = len(plane_clusters[:num_planes]) + 1  # +1 for the non-planar group

        print(f"  [PLANES] Final segmentation: {num_planes} groups")

        plane_colors = np.random.rand(num_planes, 3)

        # Compute mean normals for each final segment
        final_cluster_normals = []
        for segment_id in range(num_planes):
            segment_mask = triangle_labels == segment_id
            if segment_mask.sum() > 0:
                mean_normal = triangle_normals[segment_mask].mean(axis=0)
                norm = np.linalg.norm(mean_normal)
                if norm > 0:
                    mean_normal = mean_normal / norm
                final_cluster_normals.append(mean_normal)
            else:
                final_cluster_normals.append(np.array([0, 0, 1]))

        final_cluster_normals = np.array(final_cluster_normals)

        # Assign vertex colors by majority vote from adjacent triangles
        vertex_colors = np.zeros((num_vertices, 3))
        vertex_label_votes = [[] for _ in range(num_vertices)]

        for tri_idx, triangle in enumerate(triangles):
            label = triangle_labels[tri_idx]
            for vertex_idx in triangle:
                vertex_label_votes[vertex_idx].append(label)

        for v_idx in range(num_vertices):
            if vertex_label_votes[v_idx]:
                label = max(set(vertex_label_votes[v_idx]),
                          key=vertex_label_votes[v_idx].count)
                vertex_colors[v_idx] = plane_colors[label]

        mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)
        o3d.io.write_triangle_mesh(str(output_path), mesh)

        plane_sizes = [int(np.sum(triangle_labels == i)) for i in range(num_planes)]

        # Compute approximate plane equations (center + normal)
        planes_info = []
        for i in range(num_planes):
            cluster_mask = triangle_labels == i
            cluster_triangles = triangles[cluster_mask]

            if len(cluster_triangles) == 0:
                continue

            cluster_vertices = vertices[cluster_triangles.flatten()]
            centroid = cluster_vertices.mean(axis=0)
            normal = final_cluster_normals[i]

            # Plane equation: ax + by + cz = d
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
    """Main entry point for mesh segmentation."""
    methods = {
        'connectivity': segment_by_connectivity,
        'sharp_edges': segment_by_sharp_edges,
        'curvature': segment_by_curvature,
        'planes': segment_by_planes
    }

    if method not in methods:
        return {
            'success': False,
            'error': f"Unknown method: {method}. Available: {list(methods.keys())}"
        }

    return methods[method](input_path, output_path, **kwargs)


def segment_mesh_glb(
    input_glb: Path,
    output_glb: Path,
    method: str = "connectivity",
    temp_dir: Path = None,
    **kwargs
) -> Dict[str, Any]:
    """Segment a GLB mesh via temporary OBJ conversion. Pipeline: GLB -> OBJ -> segment -> OBJ -> GLB."""
    if temp_dir is None:
        temp_dir = Path("data/temp")

    temp_in = None
    temp_out = None

    try:
        if not input_glb.exists():
            return {"success": False, "error": f"Input file not found: {input_glb}"}

        print(f"[SEGMENTATION-GLB] Loading GLB: {input_glb.name}")

        loaded = trimesh.load(str(input_glb))

        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                return {"success": False, "error": "Empty scene, no geometry"}
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        had_textures = (
            hasattr(mesh, 'visual') and
            hasattr(mesh.visual, 'material') and
            mesh.visual.material is not None
        )

        original_vertices = len(mesh.vertices)
        original_faces = len(mesh.faces)

        temp_in = get_temp_path("segment_in", ".obj", temp_dir)
        mesh.export(str(temp_in), file_type='obj')
        print(f"[SEGMENTATION-GLB] Temp OBJ created: {temp_in.name}")

        temp_out = get_temp_path("segment_out", ".obj", temp_dir)

        result = segment_mesh(
            input_path=temp_in,
            output_path=temp_out,
            method=method,
            **kwargs
        )

        if not result['success']:
            return result

        print(f"[SEGMENTATION-GLB] Converting result to GLB")

        o3d_mesh = o3d.io.read_triangle_mesh(str(temp_out))
        vertices = np.asarray(o3d_mesh.vertices)
        faces = np.asarray(o3d_mesh.triangles)

        vertex_colors_rgba = None
        if o3d_mesh.has_vertex_colors():
            vertex_colors = np.asarray(o3d_mesh.vertex_colors)
            # Open3D: float RGB [0,1]. Trimesh: uint8 RGBA.
            vertex_colors_rgba = np.ones((len(vertex_colors), 4), dtype=np.uint8)
            vertex_colors_rgba[:, :3] = (vertex_colors * 255).astype(np.uint8)
            vertex_colors_rgba[:, 3] = 255
            print(f"[SEGMENTATION-GLB] Vertex colors: {len(vertex_colors)} vertices")

        segmented_mesh = trimesh.Trimesh(
            vertices=vertices,
            faces=faces,
            vertex_colors=vertex_colors_rgba
        )

        segmented_mesh.export(str(output_glb), file_type='glb')

        final_vertices = len(segmented_mesh.vertices)
        final_faces = len(segmented_mesh.faces)

        print(f"[SEGMENTATION-GLB] Success: {result.get('num_segments', 0)} segments")

        return {
            **result,
            "output_filename": output_glb.name,
            "output_format": "glb",
            "original_vertices": original_vertices,
            "original_faces": original_faces,
            "vertices_count": final_vertices,
            "faces_count": final_faces,
            "had_textures": had_textures,
            "textures_lost": had_textures  # Toujours perdues après segmentation
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"GLB segmentation error: {str(e)}"
        }
    finally:
        safe_delete(temp_in)
        safe_delete(temp_out)
        # Also delete the .mtl that accompanies the .obj
        if temp_out:
            mtl_file = temp_out.with_suffix('.mtl')
            safe_delete(mtl_file)
        print(f"[SEGMENTATION-GLB] Temp files cleaned up")

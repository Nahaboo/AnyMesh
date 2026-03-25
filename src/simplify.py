"""
3D mesh simplification using pyfqmr Quadric Error Metric (QEM). GLB-first.

When preserve_texture=True, uses pymeshlab's texture-aware QEM decimation
(meshing_decimation_quadric_edge_collapse_with_texture) via OBJ round-trip.
"""

from pathlib import Path
from typing import Dict, Any
import uuid
import trimesh
import numpy as np
import pyfqmr
import pymeshlab


def _simplify_with_texture(
    input_path: Path,
    output_path: Path,
    target_triangles: int,
    temp_dir: Path
) -> Dict[str, Any]:
    """
    Texture-preserving simplification via pymeshlab QEM with UV support.
    Round-trips through OBJ to keep UV coordinates intact.
    Returns dict with keys: success, textured_mesh, error.
    """
    uid = uuid.uuid4().hex[:8]
    obj_in = temp_dir / f"simplify_{uid}_in.obj"
    tex_out = temp_dir / f"simplify_{uid}_tex.png"
    obj_out = temp_dir / f"simplify_{uid}_out.obj"

    try:
        # 1. Load GLB and extract texture
        loaded = trimesh.load(str(input_path), force='scene')
        if hasattr(loaded, 'geometry'):
            mesh = list(loaded.geometry.values())[0]
        else:
            mesh = loaded

        if not hasattr(mesh.visual, 'material') or \
           not hasattr(mesh.visual.material, 'baseColorTexture') or \
           mesh.visual.material.baseColorTexture is None:
            return {'success': False, 'error': 'No baseColorTexture found'}

        texture = mesh.visual.material.baseColorTexture.copy()
        texture.save(str(tex_out))
        texture.close()

        # 2. Export to OBJ with MTL pointing to texture
        # trimesh OBJ export writes UVs (vt) and MTL automatically
        export_bytes = mesh.export(file_type='obj')
        obj_in.write_bytes(export_bytes if isinstance(export_bytes, bytes) else export_bytes.encode())

        # Write MTL manually to ensure texture reference is correct
        mtl_path = obj_in.with_suffix('.mtl')
        mtl_path.write_text(
            f"newmtl material0\n"
            f"map_Kd {tex_out.name}\n"
        )
        # Patch OBJ to reference our MTL
        obj_text = obj_in.read_text(errors='replace')
        if 'mtllib' not in obj_text:
            obj_text = f"mtllib {mtl_path.name}\n" + obj_text
            obj_in.write_text(obj_text)

        print(f"[SIMPLIFY] OBJ exported: {obj_in.name}, texture: {tex_out.name}")

        # 3. pymeshlab texture-aware decimation
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(obj_in))

        n_faces_before = ms.current_mesh().face_number()
        print(f"[SIMPLIFY] pymeshlab loaded: {n_faces_before} faces, target: {target_triangles}")

        ms.meshing_decimation_quadric_edge_collapse_with_texture(
            targetfacenum=target_triangles,
            qualitythr=0.3,
            extratcoordw=1.0,
            preserveboundary=True,
            boundaryweight=1.0,
            optimalplacement=True,
            preservenormal=True,
        )

        n_faces_after = ms.current_mesh().face_number()
        print(f"[SIMPLIFY] pymeshlab result: {n_faces_after} faces")

        # 4. Save OBJ and reload with trimesh
        ms.save_current_mesh(str(obj_out), save_wedge_texcoord=True)

        result_mesh = trimesh.load(str(obj_out), force='mesh')
        if hasattr(result_mesh, 'geometry'):
            result_mesh = list(result_mesh.geometry.values())[0]

        # Re-attach texture if trimesh dropped it
        if not hasattr(result_mesh.visual, 'material') or \
           not hasattr(result_mesh.visual.material, 'baseColorTexture') or \
           result_mesh.visual.material.baseColorTexture is None:
            from PIL import Image
            img = Image.open(str(tex_out)).copy()
            material = trimesh.visual.material.PBRMaterial(
                baseColorTexture=img,
                name='diffuse'
            )
            if hasattr(result_mesh.visual, 'uv') and result_mesh.visual.uv is not None:
                result_mesh.visual = trimesh.visual.TextureVisuals(
                    uv=result_mesh.visual.uv,
                    material=material
                )

        return {'success': True, 'textured_mesh': result_mesh}

    except Exception as e:
        return {'success': False, 'error': str(e)}

    finally:
        for f in [obj_in, obj_out, tex_out,
                  obj_in.with_suffix('.mtl'), obj_out.with_suffix('.mtl')]:
            if f.exists():
                f.unlink()


def simplify_mesh_glb(
    input_path: Path,
    output_path: Path,
    target_triangles: int = None,
    reduction_ratio: float = None,
    preserve_texture: bool = False,
    temp_dir: Path = Path("data/temp")
) -> Dict[str, Any]:
    """
    Simplify a GLB using Quadric Error Metric.

    preserve_texture=False: pyfqmr only (fast, no UV).
    preserve_texture=True: pymeshlab texture-aware QEM via OBJ round-trip.
    target_triangles takes priority over reduction_ratio.
    """
    try:
        if not input_path.exists():
            return {'success': False, 'error': f"File not found: {input_path}"}

        if target_triangles is None and reduction_ratio is None:
            return {'success': False, 'error': "Specify target_triangles or reduction_ratio"}

        loaded = trimesh.load(str(input_path))

        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if not meshes:
                return {'success': False, 'error': 'Empty scene, no geometry'}
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            return {'success': False, 'error': 'No valid vertices'}
        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            return {'success': False, 'error': 'No valid faces'}

        has_textures = (
            hasattr(mesh, 'visual') and
            hasattr(mesh.visual, 'material') and
            mesh.visual.material is not None
        )

        original_vertices = len(mesh.vertices)
        original_triangles = len(mesh.faces)

        if target_triangles is None:
            target_triangles = int(original_triangles * (1 - reduction_ratio))
        target_triangles = max(4, min(int(target_triangles), original_triangles))

        texture_transferred = False

        if preserve_texture and has_textures:
            result = _simplify_with_texture(input_path, output_path, target_triangles, temp_dir)
            if result['success']:
                result['textured_mesh'].export(str(output_path), file_type='glb')
                texture_transferred = True
                mesh_simplified = result['textured_mesh']
            else:
                print(f"[SIMPLIFY] Texture-aware simplification failed: {result.get('error')} — falling back to pyfqmr")
                preserve_texture = False

        if not texture_transferred:
            # preserve_border=True protects open boundary edges
            simplifier = pyfqmr.Simplify()
            simplifier.setMesh(
                mesh.vertices.astype(np.float64),
                mesh.faces.astype(np.int32)
            )
            simplifier.simplify_mesh(
                target_count=target_triangles,
                aggressiveness=7,
                preserve_border=True,
                verbose=False,
            )
            verts, faces, _ = simplifier.getMesh()
            mesh_simplified = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
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
            'has_textures': has_textures,
            'textures_lost': has_textures and not texture_transferred,
            'texture_transferred': texture_transferred
        }

    except Exception as e:
        return {'success': False, 'error': f"Erreur simplification GLB: {str(e)}"}

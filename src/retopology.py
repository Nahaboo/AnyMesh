"""
3D mesh retopology using Instant Meshes CLI.
"""

import subprocess
import platform
import trimesh
from pathlib import Path
from typing import Dict, Any


# Instant Meshes path differs between Windows and Linux (Docker)
if platform.system() == "Windows":
    INSTANT_MESHES_PATH = Path("tools/instant-meshes/Instant Meshes.exe")
else:
    INSTANT_MESHES_PATH = Path("/app/tools/instant-meshes/Instant Meshes")

import numpy as np
import pymeshlab
from .temp_utils import get_temp_path, safe_delete


def retopologize_mesh(
    input_path: Path,
    output_path: Path,
    target_face_count: int = 10000,
    deterministic: bool = True,
    preserve_boundaries: bool = True,
    timeout: int = 300
) -> Dict[str, Any]:
    """Retopologize a mesh using Instant Meshes CLI."""

    if not input_path.exists():
        return {
            "success": False,
            "error": f"Input file not found: {input_path}"
        }

    try:
        original_mesh = trimesh.load(str(input_path))
        original_vertices = len(original_mesh.vertices)
        original_faces = len(original_mesh.faces)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load original mesh: {str(e)}"
        }

    instant_meshes_exe = INSTANT_MESHES_PATH

    if not instant_meshes_exe.exists():
        return {
            "success": False,
            "error": f"Instant Meshes executable not found at {instant_meshes_exe}"
        }

    # Instant Meshes generates quads then converts to triangles.
    # Empirical: 1 quad = 2 triangles, so target_vertices ≈ target_face_count / 2.
    target_vertices = target_face_count // 2
    cmd = [
        str(instant_meshes_exe.absolute()),
        "-o", str(output_path.absolute()),
        "-v", str(target_vertices)
    ]

    # -D: dominant mode, uses triangles where quads fail (avoids holes in complex areas)
    cmd.append("-D")
    # -S 4: more smoothing iterations for better quality
    cmd.extend(["-S", "4"])

    if deterministic:
        cmd.append("-d")

    if preserve_boundaries:
        cmd.append("-b")

    cmd.append(str(input_path.absolute()))

    print(f"[RETOPOLOGY] Executing: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=instant_meshes_exe.parent
        )

        if result.stdout:
            print(f"[RETOPOLOGY] stdout:\n{result.stdout}")
        if result.stderr:
            print(f"[RETOPOLOGY] stderr:\n{result.stderr}")

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Instant Meshes failed with code {result.returncode}: {result.stderr}"
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Retopology timeout after {timeout} seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to execute Instant Meshes: {str(e)}"
        }

    if not output_path.exists():
        return {
            "success": False,
            "error": "Output file was not created by Instant Meshes"
        }

    # Read stats from Instant Meshes stdout.
    # The generated PLY contains N-gons that Trimesh cannot read directly.
    retopo_vertices = 0
    retopo_faces = 0
    for line in result.stdout.splitlines():
        if line.startswith("Writing ") and "(V=" in line:
            # Example: Writing "..." (V=22541, F=23872) .. done.
            try:
                v_part = line.split("(V=")[1].split(",")[0]
                f_part = line.split("F=")[1].split(")")[0]
                retopo_vertices = int(v_part)
                retopo_faces = int(f_part)
            except Exception:
                pass

    return {
        "success": True,
        "output_filename": output_path.name,
        "original_vertices": original_vertices,
        "original_faces": original_faces,
        "retopo_vertices": retopo_vertices,
        "retopo_faces": retopo_faces
    }


def retopologize_mesh_glb(
    input_glb: Path,
    output_glb: Path,
    target_face_count: int = 10000,
    deterministic: bool = True,
    preserve_boundaries: bool = True,
    temp_dir: Path = None,
    bake_textures: bool = False
) -> Dict[str, Any]:
    """
    Retopologize a GLB via a temporary PLY conversion.

    Pipeline: GLB -> PLY (temp) -> Instant Meshes -> PLY (temp) -> GLB
    """
    if temp_dir is None:
        temp_dir = Path("data/temp")

    temp_in = None
    temp_out = None

    try:
        if not input_glb.exists():
            return {"success": False, "error": f"Input file not found: {input_glb}"}

        print(f"[RETOPOLOGY-GLB] Loading GLB: {input_glb.name}")

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

        temp_in = get_temp_path("retopo_in", ".ply", temp_dir)
        mesh.export(str(temp_in), file_type='ply')
        print(f"[RETOPOLOGY-GLB] Temp PLY created: {temp_in.name}")

        actual_input = temp_in

        temp_out = get_temp_path("retopo_out", ".ply", temp_dir)

        result = retopologize_mesh(
            input_path=actual_input,
            output_path=temp_out,
            target_face_count=target_face_count,
            deterministic=deterministic,
            preserve_boundaries=preserve_boundaries
        )

        if not result['success']:
            return result

        # Instant Meshes produces mixed polygons (quads, N-gons). Triangulate with pymeshlab.
        print(f"[RETOPOLOGY-GLB] Converting result to GLB")

        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(temp_out))
        ms.apply_filter('meshing_poly_to_tri')  # Triangule les N-gons
        m = ms.current_mesh()
        retopo_vertices = m.vertex_number()
        retopo_faces = m.face_number()

        if retopo_faces == 0:
            return {"success": False, "error": "Instant Meshes produced an empty mesh after triangulation"}

        retopo_mesh = trimesh.Trimesh(
            vertices=m.vertex_matrix(),
            faces=m.face_matrix(),
            process=False
        )

        bake_result = {"success": False}
        if bake_textures and had_textures:
            from .texture_baker import bake_texture
            tex_output = output_glb.parent / (output_glb.stem + "_diffuse.png")
            bake_result = bake_texture(
                high_poly_glb=input_glb,
                low_poly_mesh=retopo_mesh,
                output_texture_path=tex_output,
                texture_size=1024
            )
            if bake_result["success"]:
                retopo_mesh = bake_result["textured_mesh"]
                print(f"[RETOPOLOGY-GLB] Texture baked: {tex_output.name}")
            else:
                print(f"[RETOPOLOGY-GLB] Baking failed: {bake_result.get('error')}")

        retopo_mesh.export(str(output_glb), file_type='glb')

        print(f"[RETOPOLOGY-GLB] Success: {original_faces} -> {retopo_faces} faces")

        return {
            "success": True,
            "output_filename": output_glb.name,
            "output_format": "glb",
            "original_vertices": original_vertices,
            "original_faces": original_faces,
            "retopo_vertices": retopo_vertices,
            "retopo_faces": retopo_faces,
            "had_textures": had_textures,
            "textures_lost": had_textures and not bake_result.get("success", False),
            "texture_baked": bake_result.get("success", False),
            "baked_texture_filename": bake_result.get("texture_filename", None)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"GLB retopology error: {str(e)}"
        }
    finally:
        safe_delete(temp_in)
        safe_delete(temp_out)
        print(f"[RETOPOLOGY-GLB] Temp files cleaned up")

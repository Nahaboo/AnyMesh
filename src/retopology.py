"""
Module pour la retopologie de meshes 3D en utilisant Instant Meshes.
"""

import subprocess
import trimesh
from pathlib import Path
from typing import Dict, Any

from .temp_utils import get_temp_path, safe_delete


def retopologize_mesh(
    input_path: Path,
    output_path: Path,
    target_face_count: int = 10000,
    deterministic: bool = True,
    preserve_boundaries: bool = True,
    timeout: int = 300  # 5 minutes par défaut
) -> Dict[str, Any]:
    """
    Retopologise un mesh 3D en utilisant Instant Meshes CLI.

    Args:
        input_path: Chemin du fichier d'entrée (OBJ, PLY, STL, OFF)
        output_path: Chemin du fichier de sortie
        target_face_count: Nombre de faces cibles dans le mesh résultant
        deterministic: Si True, utilise le mode déterministe (reproductible)
        preserve_boundaries: Si True, aligne aux bordures pour les meshes ouverts
        timeout: Timeout en secondes pour l'exécution

    Returns:
        Dict contenant:
            - success: bool
            - output_filename: str
            - original_vertices: int
            - original_faces: int
            - retopo_vertices: int
            - retopo_faces: int
            - error: str (si échec)
    """

    # Vérifier que le fichier d'entrée existe
    if not input_path.exists():
        return {
            "success": False,
            "error": f"Input file not found: {input_path}"
        }

    # Charger le mesh original pour les statistiques
    try:
        original_mesh = trimesh.load(str(input_path))
        original_vertices = len(original_mesh.vertices)
        original_faces = len(original_mesh.faces)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load original mesh: {str(e)}"
        }

    # Construire la commande Instant Meshes
    instant_meshes_exe = Path("tools/instant-meshes/Instant Meshes.exe")

    if not instant_meshes_exe.exists():
        return {
            "success": False,
            "error": "Instant Meshes executable not found at tools/instant-meshes/Instant Meshes.exe"
        }

    # Arguments de la commande
    # NOTE: Instant Meshes génère un quad mesh qui est ensuite converti en triangles
    # Relation empirique: 1 quad = 2 triangles, donc pour N triangles on veut ~N/2 quads
    # Et un quad mesh a approximativement autant de vertices que de quads
    # Donc: target_vertices ≈ target_face_count / 2
    target_vertices = target_face_count // 2
    cmd = [
        str(instant_meshes_exe.absolute()),
        "-o", str(output_path.absolute()),
        "-v", str(target_vertices)
    ]

    # Options de qualité
    # -D (dominant mode) : permet d'utiliser des triangles là où les quads ne marchent pas
    # Cela évite les trous dans les zones complexes avec peu de faces
    cmd.append("-D")

    # -S 4 : augmente le nombre d'itérations de lissage pour meilleure qualité
    cmd.extend(["-S", "4"])

    # Options utilisateur
    if deterministic:
        cmd.append("-d")

    if preserve_boundaries:
        cmd.append("-b")

    # Fichier d'entrée (doit être à la fin)
    cmd.append(str(input_path.absolute()))

    print(f"[RETOPOLOGY] Executing: {' '.join(cmd)}")

    # Exécuter Instant Meshes
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=instant_meshes_exe.parent  # Exécuter depuis le dossier instant-meshes
        )

        # Afficher la sortie pour debug
        if result.stdout:
            print(f"[RETOPOLOGY] stdout:\n{result.stdout}")
        if result.stderr:
            print(f"[RETOPOLOGY] stderr:\n{result.stderr}")

        # Vérifier le code de sortie
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

    # Vérifier que le fichier de sortie a été créé
    if not output_path.exists():
        return {
            "success": False,
            "error": "Output file was not created by Instant Meshes"
        }

    # Charger le mesh résultant pour les statistiques
    try:
        # Trimesh peut avoir des problèmes avec certains PLY générés par Instant Meshes
        # On essaie d'abord avec trimesh, puis avec open3d si ça échoue
        try:
            retopo_mesh = trimesh.load(str(output_path), process=False)
            retopo_vertices = len(retopo_mesh.vertices)
            retopo_faces = len(retopo_mesh.faces)
        except Exception as trimesh_error:
            print(f"  [WARNING] Trimesh failed to load PLY: {trimesh_error}")
            print(f"  [INFO] Trying with Open3D instead...")
            import open3d as o3d
            retopo_mesh_o3d = o3d.io.read_triangle_mesh(str(output_path))
            retopo_vertices = len(retopo_mesh_o3d.vertices)
            retopo_faces = len(retopo_mesh_o3d.triangles)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load retopologized mesh: {str(e)}"
        }

    # Retourner les statistiques
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
    temp_dir: Path = None
) -> Dict[str, Any]:
    """
    GLB-First: Retopologise un GLB via conversion temporaire PLY.

    Pipeline: GLB → PLY (temp) → Instant Meshes → PLY (temp) → GLB

    Args:
        input_glb: Chemin du fichier GLB d'entrée
        output_glb: Chemin du fichier GLB de sortie
        target_face_count: Nombre de faces cibles
        deterministic: Mode déterministe (reproductible)
        preserve_boundaries: Préserver les bordures
        temp_dir: Répertoire pour fichiers temporaires (défaut: data/temp)

    Returns:
        Dict avec résultat et statistiques
    """
    if temp_dir is None:
        temp_dir = Path("data/temp")

    temp_in = None
    temp_out = None

    try:
        # 1. Vérifier l'entrée
        if not input_glb.exists():
            return {"success": False, "error": f"Input file not found: {input_glb}"}

        # 2. Charger le GLB et exporter en PLY temporaire
        print(f"[RETOPOLOGY-GLB] Loading GLB: {input_glb.name}")

        loaded = trimesh.load(str(input_glb))

        # Gérer les Scenes
        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                return {"success": False, "error": "Scene vide, aucune geometrie"}
            mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        # Détecter textures pour warning
        had_textures = (
            hasattr(mesh, 'visual') and
            hasattr(mesh.visual, 'material') and
            mesh.visual.material is not None
        )

        original_vertices = len(mesh.vertices)
        original_faces = len(mesh.faces)

        # 3. Exporter en PLY temporaire
        temp_in = get_temp_path("retopo_in", ".ply", temp_dir)
        mesh.export(str(temp_in), file_type='ply')
        print(f"[RETOPOLOGY-GLB] Temp PLY created: {temp_in.name}")

        # 4. Appeler Instant Meshes
        temp_out = get_temp_path("retopo_out", ".ply", temp_dir)

        result = retopologize_mesh(
            input_path=temp_in,
            output_path=temp_out,
            target_face_count=target_face_count,
            deterministic=deterministic,
            preserve_boundaries=preserve_boundaries
        )

        if not result['success']:
            return result

        # 5. Charger le PLY résultat et exporter en GLB
        # Note: Instant Meshes génère des quads mixtes, Trimesh peut échouer
        # On utilise Open3D comme fallback si nécessaire
        print(f"[RETOPOLOGY-GLB] Converting result to GLB")

        try:
            retopo_mesh = trimesh.load(str(temp_out), process=False)
            retopo_vertices = len(retopo_mesh.vertices)
            retopo_faces = len(retopo_mesh.faces)
        except Exception as trimesh_err:
            print(f"  [WARN] Trimesh failed to load PLY: {trimesh_err}")
            print(f"  [INFO] Using Open3D fallback...")
            import open3d as o3d
            o3d_mesh = o3d.io.read_triangle_mesh(str(temp_out))
            retopo_vertices = len(o3d_mesh.vertices)
            retopo_faces = len(o3d_mesh.triangles)

            # Convertir Open3D → Trimesh pour export GLB
            import numpy as np
            vertices = np.asarray(o3d_mesh.vertices)
            faces = np.asarray(o3d_mesh.triangles)
            retopo_mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

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
            "textures_lost": had_textures  # Toujours perdues après retopo
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"GLB retopology error: {str(e)}"
        }
    finally:
        # 6. Nettoyer les fichiers temporaires
        safe_delete(temp_in)
        safe_delete(temp_out)
        print(f"[RETOPOLOGY-GLB] Temp files cleaned up")

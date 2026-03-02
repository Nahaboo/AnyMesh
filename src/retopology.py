"""
Module pour la retopologie de meshes 3D en utilisant Instant Meshes.
"""

import subprocess
import platform
import trimesh
from pathlib import Path
from typing import Dict, Any


# Chemin Instant Meshes adaptatif selon l'OS
if platform.system() == "Windows":
    INSTANT_MESHES_PATH = Path("tools/instant-meshes/Instant Meshes.exe")
else:
    # Linux (Docker production)
    INSTANT_MESHES_PATH = Path("/app/tools/instant-meshes/Instant Meshes")

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

    # Utiliser le chemin Instant Meshes adaptatif (Windows/Linux)
    instant_meshes_exe = INSTANT_MESHES_PATH

    if not instant_meshes_exe.exists():
        return {
            "success": False,
            "error": f"Instant Meshes executable not found at {instant_meshes_exe}"
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

    # Lire les stats depuis le log stdout d'Instant Meshes
    # (le PLY généré contient des N-gons que Trimesh ne peut pas lire)
    retopo_vertices = 0
    retopo_faces = 0
    for line in result.stdout.splitlines():
        if line.startswith("Writing ") and "(V=" in line:
            # Ex: Writing "..." (V=22541, F=23872) .. done.
            try:
                v_part = line.split("(V=")[1].split(",")[0]
                f_part = line.split("F=")[1].split(")")[0]
                retopo_vertices = int(v_part)
                retopo_faces = int(f_part)
            except Exception:
                pass

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
    temp_dir: Path = None,
    sanitize: bool = False,
    bake_textures: bool = False
) -> Dict[str, Any]:
    """
    GLB-First: Retopologise un GLB via conversion temporaire PLY.

    Pipeline: GLB → PLY (temp) → [Sanitize watertight?] → Instant Meshes → PLY (temp) → GLB

    Args:
        input_glb: Chemin du fichier GLB d'entrée
        output_glb: Chemin du fichier GLB de sortie
        target_face_count: Nombre de faces cibles
        deterministic: Mode déterministe (reproductible)
        preserve_boundaries: Préserver les bordures
        temp_dir: Répertoire pour fichiers temporaires (défaut: data/temp)
        sanitize: Si True, tente de rendre le mesh watertight via pymeshfix.
                  Désactivé par défaut car les meshes TRELLIS sont multi-composantes
                  par design (>700 composantes pour un vaisseau) — pymeshfix bouche
                  chaque bord séparément ce qui détruit la forme. N'activer que pour
                  des meshes avec peu de composantes (scans, meshes manuels).

    Returns:
        Dict avec résultat et statistiques
    """
    if temp_dir is None:
        temp_dir = Path("data/temp")

    temp_in = None
    temp_out = None
    temp_sanitized = None

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

        # 3b. Sanitize : réparer la topologie avec pymeshfix (préserve la forme)
        # Auto-détection : désactiver si trop de composantes (mesh multi-composantes TRELLIS)
        san_result = {"success": False}
        sanitized_glb = None  # Chemin GLB du mesh sanitizé (pour visualisation)
        if sanitize:
            components = len(mesh.split(only_watertight=False))
            if components > 10:
                print(f"[RETOPOLOGY-GLB] Sanitization skipped: {components} components detected (multi-component mesh, pymeshfix would destroy shape)")
                sanitize = False
            try:
                import pymeshfix
                import numpy as np
                meshfix = pymeshfix.MeshFix(
                    np.array(mesh.vertices),
                    np.array(mesh.faces)
                )
                meshfix.repair()
                san_mesh = trimesh.Trimesh(
                    vertices=meshfix.points,
                    faces=meshfix.faces,
                    process=False
                )
                san_result = {
                    "success": True,
                    "is_watertight": san_mesh.is_watertight,
                    "faces": len(san_mesh.faces)
                }
                print(f"[RETOPOLOGY-GLB] Sanitized: watertight={san_mesh.is_watertight}, faces={len(san_mesh.faces)}")

                # Exporter le mesh réparé en PLY temporaire pour Instant Meshes
                temp_sanitized = get_temp_path("retopo_sanitized", ".ply", temp_dir)
                san_mesh.export(str(temp_sanitized), file_type='ply')
                actual_input = temp_sanitized

                # Sauvegarder une copie GLB pour visualisation
                sanitized_glb = output_glb.parent / (output_glb.stem.replace("_retopo", "") + "_sanitized.glb")
                san_mesh.export(str(sanitized_glb), file_type='glb')
                print(f"[RETOPOLOGY-GLB] Sanitized mesh saved: {sanitized_glb.name}")

            except Exception as e:
                print(f"[RETOPOLOGY-GLB] Sanitization failed ({e}), using original PLY")
                actual_input = temp_in
        else:
            actual_input = temp_in

        # 4. Appeler Instant Meshes
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

        # 5. Charger le PLY résultat et exporter en GLB
        # Instant Meshes génère des polygones mixtes (quads, N-gons) → pymeshlab pour triangulation
        print(f"[RETOPOLOGY-GLB] Converting result to GLB")

        import pymeshlab
        import numpy as np

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

        # 5b. Baking optionnel : transférer la texture high poly → low poly
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
            "sanitized": san_result.get("is_watertight", False) if sanitize and san_result.get("success") else False,
            "sanitized_filename": sanitized_glb.name if sanitized_glb else None,
            "texture_baked": bake_result.get("success", False),
            "baked_texture_filename": bake_result.get("texture_filename", None)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"GLB retopology error: {str(e)}"
        }
    finally:
        # 6. Nettoyer les fichiers temporaires
        safe_delete(temp_in)
        safe_delete(temp_sanitized)
        safe_delete(temp_out)
        print(f"[RETOPOLOGY-GLB] Temp files cleaned up")

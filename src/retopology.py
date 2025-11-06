"""
Module pour la retopologie de meshes 3D en utilisant Instant Meshes.
"""

import subprocess
import trimesh
from pathlib import Path
from typing import Dict, Any


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
        retopo_mesh = trimesh.load(str(output_path))
        retopo_vertices = len(retopo_mesh.vertices)
        retopo_faces = len(retopo_mesh.faces)
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

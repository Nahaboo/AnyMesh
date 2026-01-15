"""
Module de conversion de maillages 3D vers GLB avec compression Draco
Convertit tous les formats (OBJ, STL, PLY, OFF) en GLB optimisé pour Three.js
"""

import os
import subprocess
from pathlib import Path
import trimesh


def convert_to_glb(input_path: Path, output_path: Path) -> dict:
    """
    Convertit un fichier 3D (OBJ, STL, PLY, OFF) en GLB

    Args:
        input_path: Chemin du fichier source
        output_path: Chemin du fichier GLB de sortie

    Returns:
        dict: Statistiques de la conversion {
            'success': bool,
            'input_format': str,
            'output_size': int (bytes),
            'vertices': int,
            'triangles': int,
            'conversion_time_ms': float,
            'error': str (si échec)
        }
    """
    import time
    start_time = time.time()

    try:
        # Charger le mesh avec Trimesh
        print(f"   Converting {input_path.name} to GLB...")
        loaded = trimesh.load(str(input_path))

        # Vérifier le type chargé
        print(f"   Type chargé: {type(loaded).__name__}")

        # Si c'est une Scene, extraire le premier mesh
        if hasattr(loaded, 'geometry'):
            # C'est une Scene avec potentiellement plusieurs meshes
            print(f"   Scene détectée avec {len(loaded.geometry)} géométrie(s)")
            # Fusionner toutes les géométries en un seul mesh
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                return {
                    'success': False,
                    'error': 'La scène ne contient aucune géométrie'
                }
            elif len(meshes) == 1:
                mesh = meshes[0]
            else:
                # Fusionner plusieurs meshes
                mesh = trimesh.util.concatenate(meshes)
                print(f"  🔗 {len(meshes)} meshes fusionnés")
        else:
            # C'est directement un Mesh
            mesh = loaded

        # Vérifier que le mesh est valide
        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            return {
                'success': False,
                'error': 'Le fichier ne contient pas de vertices valides'
            }

        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            return {
                'success': False,
                'error': 'Le fichier ne contient pas de faces (mesh vide ou nuage de points)'
            }

        # Extraire les statistiques avant conversion
        vertices_count = len(mesh.vertices)
        triangles_count = len(mesh.faces)
        input_format = input_path.suffix.lower()

        print(f"   Mesh: {vertices_count} vertices, {triangles_count} faces")

        # Exporter en GLB
        # Trimesh supporte l'export GLB nativement
        mesh.export(str(output_path), file_type='glb')

        # Vérifier que le fichier a été créé
        if not output_path.exists():
            return {
                'success': False,
                'error': 'Le fichier GLB n\'a pas été créé'
            }

        output_size = output_path.stat().st_size
        conversion_time = (time.time() - start_time) * 1000

        print(f"   GLB conversion: {conversion_time:.2f}ms ({output_size / 1024:.1f} KB)")

        return {
            'success': True,
            'input_format': input_format,
            'output_size': output_size,
            'vertices': vertices_count,
            'triangles': triangles_count,
            'conversion_time_ms': round(conversion_time, 2)
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Erreur lors de la conversion GLB: {str(e)}"
        }


def apply_draco_compression(glb_path: Path, compression_level: int = 7) -> dict:
    """
    Applique la compression Draco à un fichier GLB existant
    Nécessite l'installation de l'outil CLI Draco (gltf-pipeline ou draco_encoder)

    Args:
        glb_path: Chemin du fichier GLB à compresser (sera modifié in-place)
        compression_level: Niveau de compression (0-10, défaut 7)
                          0 = rapide, faible compression
                          10 = lent, compression maximale

    Returns:
        dict: Statistiques de compression {
            'success': bool,
            'original_size': int (bytes),
            'compressed_size': int (bytes),
            'compression_ratio': float (0-1),
            'compression_time_ms': float,
            'method': str ('gltf-pipeline' ou 'draco_encoder'),
            'error': str (si échec)
        }
    """
    import time
    start_time = time.time()
    temp_compressed = None  # Initialiser pour le finally

    try:
        if not glb_path.exists():
            return {
                'success': False,
                'error': f'Le fichier GLB n\'existe pas: {glb_path}'
            }

        original_size = glb_path.stat().st_size

        # Créer un fichier temporaire pour la compression
        temp_compressed = glb_path.with_suffix('.compressed.glb')

        # Méthode 1: gltf-pipeline (Node.js, plus complet)
        # Installation: npm install -g gltf-pipeline
        compression_method = None

        # Vérifier si gltf-pipeline est installé
        if _command_exists('gltf-pipeline'):
            compression_method = 'gltf-pipeline'
            cmd = [
                'gltf-pipeline',
                '-i', str(glb_path),
                '-o', str(temp_compressed),
                '-d',  # Activer compression Draco
                f'--draco.compressionLevel={compression_level}',
                '--draco.quantizePositionBits=14',
                '--draco.quantizeNormalBits=10',
                '--draco.quantizeTexcoordBits=12'
            ]

            print(f"  🗜️ Compressing with gltf-pipeline (level {compression_level})...")

        # Méthode 2: draco_encoder (C++, plus rapide mais moins flexible)
        # Note: draco_encoder ne compresse pas directement GLB, il faut extraire le mesh
        # On garde cette méthode pour référence future
        elif _command_exists('draco_encoder'):
            return {
                'success': False,
                'error': 'draco_encoder ne supporte pas directement les fichiers GLB. Utilisez gltf-pipeline.'
            }

        else:
            return {
                'success': False,
                'error': 'Outil de compression Draco non trouvé. Installez gltf-pipeline: npm install -g gltf-pipeline'
            }

        # Exécuter la commande de compression
        # Sur Windows, utiliser shell=True pour résoudre les .cmd
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # Timeout de 2 minutes
            shell=True  # Nécessaire sur Windows pour trouver gltf-pipeline.cmd
        )

        if result.returncode != 0:
            return {
                'success': False,
                'error': f'Erreur gltf-pipeline: {result.stderr}'
            }

        # Vérifier que le fichier compressé a été créé
        if not temp_compressed.exists():
            return {
                'success': False,
                'error': 'Le fichier compressé n\'a pas été créé'
            }

        compressed_size = temp_compressed.stat().st_size

        # Remplacer le fichier original par le fichier compressé
        temp_compressed.replace(glb_path)

        compression_time = (time.time() - start_time) * 1000
        compression_ratio = compressed_size / original_size
        reduction_percent = (1 - compression_ratio) * 100

        print(f"  ✓ Draco compression: {compression_time:.2f}ms")
        print(f"    {original_size / 1024:.1f} KB → {compressed_size / 1024:.1f} KB ({reduction_percent:.1f}% reduction)")

        return {
            'success': True,
            'original_size': original_size,
            'compressed_size': compressed_size,
            'compression_ratio': round(compression_ratio, 3),
            'compression_time_ms': round(compression_time, 2),
            'method': compression_method
        }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Timeout: La compression Draco a pris trop de temps (>2 minutes)'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Erreur lors de la compression Draco: {str(e)}"
        }
    finally:
        # Nettoyer le fichier temporaire si nécessaire
        if temp_compressed and temp_compressed.exists() and temp_compressed != glb_path:
            temp_compressed.unlink()


def _command_exists(command: str) -> bool:
    """
    Vérifie si une commande CLI est disponible dans le PATH

    Args:
        command: Nom de la commande à vérifier

    Returns:
        bool: True si la commande existe
    """
    try:
        # Windows utilise 'where', Unix utilise 'which'
        check_cmd = 'where' if os.name == 'nt' else 'which'
        result = subprocess.run(
            [check_cmd, command],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def convert_mesh_format(
    input_path: Path,
    output_path: Path,
    output_format: str
) -> dict:
    """
    Convertit un fichier 3D vers un autre format

    Args:
        input_path: Chemin du fichier source
        output_path: Chemin du fichier de sortie
        output_format: Format de sortie ('obj', 'stl', 'ply', 'glb')

    Returns:
        dict: Statistiques de la conversion {
            'success': bool,
            'output_file': str,
            'output_size': int (bytes),
            'vertices': int,
            'triangles': int,
            'error': str (si échec)
        }
    """
    import time
    start_time = time.time()

    try:
        # Charger le mesh avec Trimesh
        print(f"   Converting {input_path.name} to {output_format.upper()}...")
        loaded = trimesh.load(str(input_path))

        # Si c'est une Scene, extraire et fusionner les meshes
        if hasattr(loaded, 'geometry'):
            print(f"  🔍 Scene detected with {len(loaded.geometry)} geometry(ies)")
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                return {
                    'success': False,
                    'error': 'Scene contains no geometry'
                }
            elif len(meshes) == 1:
                mesh = meshes[0]
            else:
                mesh = trimesh.util.concatenate(meshes)
                print(f"  🔗 {len(meshes)} meshes merged")
        else:
            mesh = loaded

        # Vérifier que le mesh est valide
        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            return {
                'success': False,
                'error': 'File contains no valid vertices'
            }

        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            return {
                'success': False,
                'error': 'File contains no faces (empty mesh or point cloud)'
            }

        # Extraire les statistiques
        vertices_count = len(mesh.vertices)
        triangles_count = len(mesh.faces)

        print(f"   Mesh: {vertices_count} vertices, {triangles_count} faces")

        # Exporter dans le format demandé
        mesh.export(str(output_path), file_type=output_format)

        # Vérifier que le fichier a été créé
        if not output_path.exists():
            return {
                'success': False,
                'error': f'{output_format.upper()} file was not created'
            }

        output_size = output_path.stat().st_size
        conversion_time = (time.time() - start_time) * 1000

        print(f"  ✓ Conversion to {output_format.upper()}: {conversion_time:.2f}ms ({output_size / 1024:.1f} KB)")

        return {
            'success': True,
            'output_file': str(output_path),
            'output_size': output_size,
            'vertices': vertices_count,
            'triangles': triangles_count,
            'conversion_time_ms': round(conversion_time, 2)
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Error during format conversion: {str(e)}"
        }


def convert_and_compress(
    input_path: Path,
    output_path: Path,
    enable_draco: bool = True,
    compression_level: int = 7
) -> dict:
    """
    Fonction tout-en-un: Convertit vers GLB puis compresse avec Draco

    Args:
        input_path: Chemin du fichier source (OBJ, STL, PLY, OFF)
        output_path: Chemin du fichier GLB de sortie
        enable_draco: Si True, applique la compression Draco après conversion
        compression_level: Niveau de compression Draco (0-10)

    Returns:
        dict: Statistiques combinées {
            'success': bool,
            'conversion': dict,  # Résultat de convert_to_glb()
            'compression': dict | None,  # Résultat de apply_draco_compression() si activé
            'total_time_ms': float,
            'final_size': int (bytes)
        }
    """
    import time
    start_time = time.time()

    # Étape 1: Conversion vers GLB
    conversion_result = convert_to_glb(input_path, output_path)

    if not conversion_result['success']:
        return {
            'success': False,
            'conversion': conversion_result,
            'compression': None,
            'error': conversion_result.get('error')
        }

    # Étape 2: Compression Draco (optionnelle)
    compression_result = None
    if enable_draco:
        compression_result = apply_draco_compression(output_path, compression_level)

        # Si la compression échoue, on garde le GLB non compressé
        if not compression_result['success']:
            print(f"  ⚠️ Draco compression failed, keeping uncompressed GLB: {compression_result.get('error')}")

    total_time = (time.time() - start_time) * 1000
    final_size = output_path.stat().st_size if output_path.exists() else 0

    return {
        'success': True,
        'conversion': conversion_result,
        'compression': compression_result,
        'total_time_ms': round(total_time, 2),
        'final_size': final_size
    }

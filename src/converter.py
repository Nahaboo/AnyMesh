"""
Module de conversion de maillages 3D vers GLB
Architecture GLB-First: Tous les fichiers sont stockes en GLB comme format master.
"""

from pathlib import Path
import trimesh


def convert_mesh_format(
    input_path: Path,
    output_path: Path,
    output_format: str
) -> dict:
    """
    Convertit un fichier 3D vers un autre format (utilise par /export)

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
            'error': str (si echec)
        }
    """
    import time
    start_time = time.time()

    try:
        print(f"   Converting {input_path.name} to {output_format.upper()}...")
        loaded = trimesh.load(str(input_path))

        # Si c'est une Scene, extraire et fusionner les meshes
        if hasattr(loaded, 'geometry'):
            print(f"   Scene detected with {len(loaded.geometry)} geometry(ies)")
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
                print(f"   {len(meshes)} meshes merged")
        else:
            mesh = loaded

        # Verifier que le mesh est valide
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

        vertices_count = len(mesh.vertices)
        triangles_count = len(mesh.faces)

        print(f"   Mesh: {vertices_count} vertices, {triangles_count} faces")

        # Exporter dans le format demande
        mesh.export(str(output_path), file_type=output_format)

        if not output_path.exists():
            return {
                'success': False,
                'error': f'{output_format.upper()} file was not created'
            }

        output_size = output_path.stat().st_size
        conversion_time = (time.time() - start_time) * 1000

        print(f"   Conversion to {output_format.upper()}: {conversion_time:.2f}ms ({output_size / 1024:.1f} KB)")

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


def convert_any_to_glb(input_path: Path, output_path: Path) -> dict:
    """
    GLB-First: Convertit n'importe quel format 3D vers GLB.

    Cette fonction est utilisee lors de l'upload pour convertir
    tous les fichiers en GLB (format master).

    Args:
        input_path: Chemin du fichier source (OBJ, STL, PLY, OFF, GLTF, GLB)
        output_path: Chemin du fichier GLB de sortie

    Returns:
        dict: {
            'success': bool,
            'has_textures': bool,  # True si le mesh a des textures/materiaux
            'original_format': str,  # Extension originale (.obj, .stl, etc.)
            'vertices': int,
            'triangles': int,
            'error': str (si echec)
        }
    """
    import shutil

    try:
        original_format = input_path.suffix.lower()

        # Si deja GLB, copier simplement
        if original_format == '.glb':
            shutil.copy2(input_path, output_path)
            mesh = trimesh.load(str(output_path))

            # Verifier si textures presentes
            has_textures = _mesh_has_textures(mesh)

            return {
                'success': True,
                'has_textures': has_textures,
                'original_format': '.glb',
                'vertices': len(mesh.vertices) if hasattr(mesh, 'vertices') else 0,
                'triangles': len(mesh.faces) if hasattr(mesh, 'faces') else 0
            }

        # Charger le mesh
        loaded = trimesh.load(str(input_path))

        # Gerer les Scenes (plusieurs meshes)
        if hasattr(loaded, 'geometry'):
            meshes = list(loaded.geometry.values())
            if len(meshes) == 0:
                return {'success': False, 'error': 'Scene contains no geometry'}
            elif len(meshes) == 1:
                mesh = meshes[0]
            else:
                mesh = trimesh.util.concatenate(meshes)
        else:
            mesh = loaded

        # Verifier validite
        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            return {'success': False, 'error': 'No valid vertices in mesh'}
        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            return {'success': False, 'error': 'No faces in mesh (point cloud?)'}

        # Detecter textures/materiaux
        has_textures = _mesh_has_textures(mesh)

        # Exporter en GLB
        mesh.export(str(output_path), file_type='glb')

        if not output_path.exists():
            return {'success': False, 'error': 'GLB file was not created'}

        return {
            'success': True,
            'has_textures': has_textures,
            'original_format': original_format,
            'vertices': len(mesh.vertices),
            'triangles': len(mesh.faces)
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Conversion error: {str(e)}",
            'original_format': input_path.suffix.lower() if input_path else 'unknown'
        }


def _mesh_has_textures(mesh) -> bool:
    """
    Verifie si un mesh Trimesh a des textures ou materiaux.

    Returns:
        bool: True si le mesh a des donnees visuelles (textures, materiaux)
    """
    if not hasattr(mesh, 'visual'):
        return False

    visual = mesh.visual

    # Verifier si c'est un TextureVisuals avec materiau
    if hasattr(visual, 'material') and visual.material is not None:
        return True

    # Verifier si c'est un ColorVisuals avec vertex colors
    if hasattr(visual, 'vertex_colors'):
        colors = visual.vertex_colors
        if colors is not None and len(colors) > 0:
            # Verifier si ce n'est pas juste la couleur par defaut
            if hasattr(colors, 'shape') and colors.shape[0] > 0:
                return True

    return False

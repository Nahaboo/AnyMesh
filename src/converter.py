"""
3D mesh format conversion. GLB-first: all files are stored as GLB.
"""

from pathlib import Path
import trimesh


def convert_mesh_format(
    input_path: Path,
    output_path: Path,
    output_format: str
) -> dict:
    """Convert a 3D file to the requested format. Used by /export."""
    import time
    start_time = time.time()

    try:
        print(f"   Converting {input_path.name} to {output_format.upper()}...")
        loaded = trimesh.load(str(input_path))

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
    """Convert any 3D format to GLB. Called on upload to normalize all files to GLB."""
    import shutil

    try:
        original_format = input_path.suffix.lower()

        if original_format == '.glb':
            shutil.copy2(input_path, output_path)
            loaded = trimesh.load(str(output_path))
            has_textures = _scene_has_textures(loaded)

            if hasattr(loaded, 'geometry'):
                meshes = list(loaded.geometry.values())
                n_verts = sum(len(m.vertices) for m in meshes if hasattr(m, 'vertices'))
                n_faces = sum(len(m.faces) for m in meshes if hasattr(m, 'faces'))
            else:
                n_verts = len(loaded.vertices) if hasattr(loaded, 'vertices') else 0
                n_faces = len(loaded.faces) if hasattr(loaded, 'faces') else 0

            return {
                'success': True,
                'has_textures': has_textures,
                'original_format': '.glb',
                'vertices': n_verts,
                'triangles': n_faces
            }

        loaded = trimesh.load(str(input_path))

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

        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            return {'success': False, 'error': 'No valid vertices in mesh'}
        if not hasattr(mesh, 'faces') or len(mesh.faces) == 0:
            return {'success': False, 'error': 'No faces in mesh (point cloud?)'}

        has_textures = _mesh_has_textures(mesh)
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


def _scene_has_textures(loaded) -> bool:
    """Return True if any geometry in the scene has textures."""
    if hasattr(loaded, 'geometry'):
        return any(_mesh_has_textures(m) for m in loaded.geometry.values())
    return _mesh_has_textures(loaded)


def _mesh_has_textures(mesh) -> bool:
    """Return True if the mesh has texture or material data."""
    if not hasattr(mesh, 'visual'):
        return False

    visual = mesh.visual

    if hasattr(visual, 'material') and visual.material is not None:
        return True

    if hasattr(visual, 'vertex_colors'):
        colors = visual.vertex_colors
        if colors is not None and len(colors) > 0:
            if hasattr(colors, 'shape') and colors.shape[0] > 0:
                return True

    return False

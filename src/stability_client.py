"""
Stability AI Fast 3D mesh generation client. Generates GLB meshes from images via the Stability AI API.
"""

import time
from pathlib import Path
from typing import Dict, Optional
import httpx
import trimesh
from PIL import Image


STABILITY_API_URL = "https://api.stability.ai/v2beta/3d/stable-fast-3d"

# Resolution to Stability API parameter mapping
RESOLUTION_PARAMS = {
    'low': {
        'texture_resolution': 512,
        'vertex_count': 5000,
        'remesh': 'triangle'
    },
    'medium': {
        'texture_resolution': 1024,
        'vertex_count': 10000,
        'remesh': 'none'
    },
    'high': {
        'texture_resolution': 2048,
        'vertex_count': -1,  # Unlimited
        'remesh': 'none'
    }
}


class StabilityAPIError(Exception):
    """Raised when the Stability API returns an error."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Stability API Error {status_code}: {message}")


def _translate_error(status_code: int, api_message: str) -> str:
    """Return a user-facing error message for the given API status code."""
    ERROR_MESSAGES = {
        400: "Invalid image or rejected by content filter",
        401: "Invalid API key - check STABILITY_API_KEY in .env",
        402: "Insufficient API credits - top up your Stability AI account",
        429: "Rate limit reached - retry in a few seconds",
        500: "Stability AI server error - retry later",
        503: "Stability AI service temporarily unavailable"
    }

    user_message = ERROR_MESSAGES.get(status_code, f"API error ({status_code})")
    return f"{user_message} | Details: {api_message}"


def _call_stability_api(
    image_path: Path,
    texture_resolution: int,
    foreground_ratio: float,
    remesh: str,
    vertex_count: int,
    api_key: str
) -> bytes:
    """
    Low-level Stability API call. Returns raw GLB bytes.

    Raises StabilityAPIError on non-200 responses.
    """
    print(f"  [STABILITY-API] Calling Fast 3D API")
    print(f"    Image: {image_path.name}")
    print(f"    Texture resolution: {texture_resolution}px")
    print(f"    Vertex count: {vertex_count if vertex_count > 0 else 'unlimited'}")
    print(f"    Remesh: {remesh}")

    with open(image_path, 'rb') as img_file:
        files = {'image': (image_path.name, img_file, 'image/jpeg')}
        data = {
            'texture_resolution': str(texture_resolution),
            'foreground_ratio': str(foreground_ratio),
            'remesh': remesh,
            'vertex_count': str(vertex_count)
        }
        headers = {'authorization': api_key}

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                STABILITY_API_URL,
                files=files,
                data=data,
                headers=headers
            )

        if response.status_code == 200:
            file_size_kb = len(response.content) / 1024
            print(f"  [OK] API call successful, received {file_size_kb:.1f} KB")
            return response.content
        else:
            try:
                error_json = response.json()
                error_message = error_json.get('message', response.text)
            except:
                error_message = response.text

            raise StabilityAPIError(
                status_code=response.status_code,
                message=error_message
            )


def generate_mesh_from_image_sf3d(
    image_path: Path,
    output_path: Path,
    resolution: str = "medium",
    remesh_option: str = None,
    api_key: Optional[str] = None
) -> Dict:
    """
    Generate a 3D mesh from an image using Stability AI Fast 3D.

    GLB-First: the API returns GLB natively, so output_path must be a .glb.
    """
    start_time = time.time()

    if not api_key:
        return {
            'success': False,
            'error': 'STABILITY_API_KEY missing - check your .env file'
        }

    if resolution not in RESOLUTION_PARAMS:
        return {
            'success': False,
            'error': f"Invalid resolution: {resolution}. Use 'low', 'medium', or 'high'"
        }

    params = RESOLUTION_PARAMS[resolution]

    if remesh_option is not None:
        params = params.copy()  # Don't mutate the global dict
        params['remesh'] = remesh_option

    print(f"\n [STABILITY-MESH] Generating mesh from image")
    print(f"  Input: {image_path.name}")
    print(f"  Resolution: {resolution}")
    print(f"  Remesh: {params['remesh']}")

    try:
        try:
            img = Image.open(image_path)
            img.verify()
            print(f"  Image validated: {img.size[0]}x{img.size[1]}px")
        except Exception as e:
            return {
                'success': False,
                'error': f"Invalid image: {str(e)}"
            }

        glb_bytes = _call_stability_api(
            image_path=image_path,
            texture_resolution=params['texture_resolution'],
            foreground_ratio=0.85,
            remesh=params['remesh'],
            vertex_count=params['vertex_count'],
            api_key=api_key
        )

        # GLB-First: save directly, no conversion needed
        if output_path.suffix.lower() != '.glb':
            output_path = output_path.with_suffix('.glb')

        print(f"  [GLB-First] Saving GLB directly to {output_path.name}")
        output_path.write_bytes(glb_bytes)
        final_output = output_path

        mesh = trimesh.load(str(final_output))
        if hasattr(mesh, 'geometry'):
            meshes = list(mesh.geometry.values())
            if len(meshes) > 0:
                mesh = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)

        vertices_count = len(mesh.vertices)
        faces_count = len(mesh.faces)
        generation_time = (time.time() - start_time) * 1000

        print(f"  [OK] Mesh generated successfully")
        print(f"    Vertices: {vertices_count}")
        print(f"    Faces: {faces_count}")
        print(f"    Total time: {generation_time:.2f}ms")

        return {
            'success': True,
            'output_file': str(final_output),
            'vertices_count': vertices_count,
            'faces_count': faces_count,
            'resolution': resolution,
            'generation_time_ms': round(generation_time, 2),
            'api_credits_used': 10,  # SF3D costs 10 credits per generation
            'method': 'stability_fast3d',
            'texture_resolution': params['texture_resolution'],
            'vertex_count': params['vertex_count']
        }

    except httpx.TimeoutException:
        return {
            'success': False,
            'error': "Timeout: Stability API did not respond within 2 minutes"
        }

    except httpx.NetworkError as e:
        return {
            'success': False,
            'error': f"Network error: {str(e)}"
        }

    except StabilityAPIError as e:
        return {
            'success': False,
            'error': _translate_error(e.status_code, e.message)
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error: {str(e)}",
            'error_type': type(e).__name__
        }

"""
Stability AI Fast 3D mesh generation client
Genere des maillages 3D de haute qualite a partir d'images en utilisant l'API Stability AI
"""

import time
from pathlib import Path
from typing import Dict, Optional
import httpx
import trimesh
from PIL import Image


STABILITY_API_URL = "https://api.stability.ai/v2beta/3d/stable-fast-3d"

# Mapping resolution vers parametres API Stability
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
    """Exception personnalisee pour les erreurs API Stability"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Stability API Error {status_code}: {message}")


def _translate_error(status_code: int, api_message: str) -> str:
    """
    Convertit les erreurs API en messages utilisateur francais

    Args:
        status_code: Code HTTP de l'erreur
        api_message: Message original de l'API

    Returns:
        Message d'erreur traduit
    """
    ERROR_MESSAGES = {
        400: "Image invalide ou rejetee par le filtre de contenu",
        401: "Cle API invalide - Verifiez STABILITY_API_KEY dans .env",
        402: "Credits API insuffisants - Rechargez votre compte Stability AI",
        429: "Limite de debit atteinte - Reessayez dans quelques secondes",
        500: "Erreur serveur Stability AI - Reessayez plus tard",
        503: "Service Stability AI temporairement indisponible"
    }

    user_message = ERROR_MESSAGES.get(status_code, f"Erreur API ({status_code})")
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
    Appel API Stability de bas niveau - retourne les bytes GLB

    Args:
        image_path: Chemin vers l'image d'entree
        texture_resolution: 512, 1024, ou 2048
        foreground_ratio: 0.1-1.0 (defaut 0.85)
        remesh: 'none', 'quad', ou 'triangle'
        vertex_count: -1 (illimite) ou nombre specifique
        api_key: Cle API Stability

    Returns:
        bytes: Contenu du fichier GLB

    Raises:
        StabilityAPIError: L'API a retourne une erreur
        httpx.TimeoutException: La requete a expire
        httpx.NetworkError: Erreur de connexion reseau
    """
    print(f"  [STABILITY-API] Calling Fast 3D API")
    print(f"    Image: {image_path.name}")
    print(f"    Texture resolution: {texture_resolution}px")
    print(f"    Vertex count: {vertex_count if vertex_count > 0 else 'unlimited'}")
    print(f"    Remesh: {remesh}")

    with open(image_path, 'rb') as img_file:
        # Preparer les donnees multipart/form-data
        files = {'image': (image_path.name, img_file, 'image/jpeg')}
        data = {
            'texture_resolution': str(texture_resolution),
            'foreground_ratio': str(foreground_ratio),
            'remesh': remesh,
            'vertex_count': str(vertex_count)
        }
        headers = {'authorization': api_key}

        # Effectuer l'appel API avec timeout
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                STABILITY_API_URL,
                files=files,
                data=data,
                headers=headers
            )

        # Verifier le statut de la reponse
        if response.status_code == 200:
            file_size_kb = len(response.content) / 1024
            print(f"  [OK] API call successful, received {file_size_kb:.1f} KB")
            return response.content
        else:
            # Parser la reponse d'erreur
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
    Genere un maillage 3D a partir d'une image en utilisant Stability AI Fast 3D

    Args:
        image_path: Chemin vers l'image d'entree (JPG/PNG)
        output_path: Chemin de sortie desire (.glb, .obj, .stl, .ply)
        resolution: 'low', 'medium', ou 'high'
        remesh_option: 'none', 'triangle', ou 'quad' - Topologie du mesh (None = auto selon resolution)
        api_key: Cle API Stability (requis)

    Returns:
        Dict avec resultats de generation:
        {
            'success': bool,
            'output_file': str,
            'vertices_count': int,
            'faces_count': int,
            'resolution': str,
            'generation_time_ms': float,
            'api_credits_used': int,
            'method': 'stability_fast3d',
            'texture_resolution': int,
            'vertex_count': int,
            'error': str (si echec)
        }
    """
    start_time = time.time()

    # Valider la cle API
    if not api_key:
        return {
            'success': False,
            'error': 'STABILITY_API_KEY manquante - Verifiez votre fichier .env'
        }

    # Valider la resolution
    if resolution not in RESOLUTION_PARAMS:
        return {
            'success': False,
            'error': f"Resolution invalide: {resolution}. Utilisez 'low', 'medium', ou 'high'"
        }

    # Obtenir les parametres pour la resolution
    params = RESOLUTION_PARAMS[resolution]

    # Surcharger remesh si specifie
    if remesh_option is not None:
        params = params.copy()  # Ne pas modifier le dict global
        params['remesh'] = remesh_option

    print(f"\n [STABILITY-MESH] Generating mesh from image")
    print(f"  Input: {image_path.name}")
    print(f"  Resolution: {resolution}")
    print(f"  Remesh: {params['remesh']}")

    try:
        # Valider l'image d'entree
        try:
            img = Image.open(image_path)
            img.verify()
            print(f"  Image validated: {img.size[0]}x{img.size[1]}px")
        except Exception as e:
            return {
                'success': False,
                'error': f"Image invalide: {str(e)}"
            }

        # Appeler l'API Stability
        glb_bytes = _call_stability_api(
            image_path=image_path,
            texture_resolution=params['texture_resolution'],
            foreground_ratio=0.85,  # Valeur recommandee par defaut
            remesh=params['remesh'],
            vertex_count=params['vertex_count'],
            api_key=api_key
        )

        # Determiner si une conversion de format est necessaire
        requested_format = output_path.suffix.lower().lstrip('.')

        if requested_format == 'glb':
            # Sauvegarde directe - pas de conversion necessaire
            print(f"  Saving GLB directly to {output_path.name}")
            output_path.write_bytes(glb_bytes)
            final_output = output_path

        else:
            # Sauvegarder vers GLB temporaire, convertir au format demande
            temp_glb = output_path.parent / f"{output_path.stem}_temp.glb"
            print(f"  Saving temporary GLB for conversion...")
            temp_glb.write_bytes(glb_bytes)

            # Convertir en utilisant le convertisseur existant
            from .converter import convert_mesh_format
            print(f"  Converting GLB to {requested_format.upper()}...")
            conversion_result = convert_mesh_format(
                input_path=temp_glb,
                output_path=output_path,
                output_format=requested_format
            )

            # Nettoyer le fichier temporaire
            temp_glb.unlink()

            if not conversion_result['success']:
                return {
                    'success': False,
                    'error': f"Conversion vers {requested_format.upper()} echouee: {conversion_result.get('error')}"
                }

            final_output = output_path

        # Charger le maillage pour les statistiques
        mesh = trimesh.load(str(final_output))
        if hasattr(mesh, 'geometry'):
            # Scene avec plusieurs maillages
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
            'api_credits_used': 10,  # SF3D coute 10 credits par generation
            'method': 'stability_fast3d',
            'texture_resolution': params['texture_resolution'],
            'vertex_count': params['vertex_count']
        }

    except httpx.TimeoutException:
        return {
            'success': False,
            'error': "Timeout: L'API Stability n'a pas repondu en 2 minutes"
        }

    except httpx.NetworkError as e:
        return {
            'success': False,
            'error': f"Erreur reseau: {str(e)}"
        }

    except StabilityAPIError as e:
        return {
            'success': False,
            'error': _translate_error(e.status_code, e.message)
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Erreur inattendue: {str(e)}",
            'error_type': type(e).__name__
        }

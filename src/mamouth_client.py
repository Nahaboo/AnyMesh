"""
Mamouth.ai text-to-image generation client
Genere des images a partir de prompts textuels via l'API Mamouth.ai (OpenAI-compatible)
"""

import time
import base64
from pathlib import Path
from typing import Dict, Optional
import httpx
from PIL import Image


MAMOUTH_API_URL = "https://api.mammouth.ai/v1/chat/completions"
DEFAULT_MODEL = "gemini-2.5-flash-image"
PHYSICS_MODEL = "gemini-2.5-flash"  # Text-only, cheap

# Mapping resolution vers taille d'image
RESOLUTION_PARAMS = {
    'low': 512,
    'medium': 1024,
    'high': 2048
}


class MamouthAPIError(Exception):
    """Exception personnalisee pour les erreurs API Mamouth"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Mamouth API Error {status_code}: {message}")


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
        400: "Prompt invalide ou rejete par le filtre de contenu",
        401: "Cle API invalide - Verifiez MAMOUTH_API_KEY dans .env",
        402: "Credits API insuffisants - Rechargez votre compte Mamouth",
        429: "Limite de debit atteinte - Reessayez dans quelques secondes",
        500: "Erreur serveur Mamouth.ai - Reessayez plus tard",
        503: "Service Mamouth.ai temporairement indisponible"
    }

    user_message = ERROR_MESSAGES.get(status_code, f"Erreur API ({status_code})")
    return f"{user_message} | Details: {api_message}"


def _call_mamouth_api(
    prompt: str,
    model: str,
    api_key: str,
    suffix: str = ""
) -> bytes:
    """
    Appel API Mamouth de bas niveau - retourne les bytes de l'image

    L'API Mamouth utilise un format OpenAI-compatible (chat.completions)
    avec les images retournees en base64 dans le champ images[].image_url.url

    Args:
        prompt: Description textuelle de l'image
        model: Nom du modele Mamouth
        api_key: Cle API Mamouth

    Returns:
        bytes: Contenu de l'image PNG

    Raises:
        MamouthAPIError: L'API a retourne une erreur
        httpx.TimeoutException: La requete a expire
        httpx.NetworkError: Erreur de connexion reseau
    """
    print(f"  [MAMOUTH-API] Calling text-to-image API")
    print(f"    Model: {model}")
    print(f"    Prompt: {prompt[:100]}...")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    # Format OpenAI-compatible chat completions
    # Append suffix directly in user prompt (system role may be ignored by some models)
    full_prompt = f"{prompt}. {suffix}" if suffix else prompt
    payload = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': full_prompt
            }
        ]
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            MAMOUTH_API_URL,
            json=payload,
            headers=headers
        )

    if response.status_code == 200:
        data = response.json()

        # Extraire l'image depuis la reponse
        # Format: choices[0].message.images[0].image_url.url = "data:image/png;base64,..."
        try:
            message = data['choices'][0]['message']
            images = message.get('images', [])

            if not images:
                # Debug: log what the model actually returned
                content = message.get('content', '')
                print(f"  [DEBUG] No images in response. Content: {content[:200]}")
                raise MamouthAPIError(500, "Pas d'image dans la reponse API")

            image_url = images[0]['image_url']['url']

            # Decoder le base64 (retirer le prefixe data:image/png;base64,)
            if ',' in image_url:
                image_data = image_url.split(',', 1)[1]
            else:
                image_data = image_url

            image_bytes = base64.b64decode(image_data)
            print(f"  [OK] Image received: {len(image_bytes) / 1024:.1f} KB")
            return image_bytes

        except (KeyError, IndexError) as e:
            raise MamouthAPIError(500, f"Format de reponse inattendu: {e}")

    else:
        try:
            error_json = response.json()
            error_message = error_json.get('error', {}).get('message', response.text)
        except Exception:
            error_message = response.text

        raise MamouthAPIError(
            status_code=response.status_code,
            message=error_message
        )


def generate_image_from_prompt(
    prompt: str,
    output_path: Path,
    resolution: str = "medium",
    api_key: Optional[str] = None
) -> Dict:
    """
    Genere une image a partir d'un prompt textuel via Mamouth.ai

    Args:
        prompt: Description textuelle de l'image souhaitee
        output_path: Chemin de sortie pour sauvegarder l'image PNG
        resolution: 'low', 'medium', ou 'high'
        api_key: Cle API Mamouth (requis)

    Returns:
        Dict avec resultats de generation:
        {
            'success': bool,
            'output_file': str,
            'prompt': str,
            'resolution': str,
            'image_width': int,
            'image_height': int,
            'generation_time_ms': float,
            'method': 'mamouth_text2img',
            'error': str (si echec)
        }
    """
    start_time = time.time()

    # Valider la cle API
    if not api_key:
        return {
            'success': False,
            'error': 'MAMOUTH_API_KEY manquante - Verifiez votre fichier .env'
        }

    # Valider la resolution
    if resolution not in RESOLUTION_PARAMS:
        return {
            'success': False,
            'error': f"Resolution invalide: {resolution}. Utilisez 'low', 'medium', ou 'high'"
        }

    # Valider le prompt
    if not prompt or len(prompt.strip()) == 0:
        return {
            'success': False,
            'error': 'Le prompt ne peut pas etre vide'
        }

    if len(prompt) > 1000:
        return {
            'success': False,
            'error': 'Le prompt est trop long (max 1000 caracteres)'
        }

    print(f"\n[MAMOUTH-IMAGE] Generating image from prompt")
    print(f"  Resolution: {resolution} ({RESOLUTION_PARAMS[resolution]}px)")

    try:
        # Appeler l'API Mamouth
        image_bytes = _call_mamouth_api(
            prompt=prompt,
            model=DEFAULT_MODEL,
            api_key=api_key,
            suffix="Plain white background, subject centered and isolated, no environment, no shadows."
        )

        # Sauvegarder sur disque
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)

        # Valider l'image sauvegardee
        img = Image.open(output_path)
        img_width, img_height = img.size

        generation_time = (time.time() - start_time) * 1000

        print(f"  [OK] Image generated successfully")
        print(f"    Size: {img_width}x{img_height}")
        print(f"    Total time: {generation_time:.0f}ms")

        return {
            'success': True,
            'output_file': str(output_path),
            'output_filename': output_path.name,
            'prompt': prompt,
            'resolution': resolution,
            'image_width': img_width,
            'image_height': img_height,
            'generation_time_ms': round(generation_time, 2),
            'method': 'mamouth_text2img'
        }

    except httpx.TimeoutException:
        return {
            'success': False,
            'error': "Timeout: L'API Mamouth n'a pas repondu en 2 minutes"
        }

    except httpx.NetworkError as e:
        return {
            'success': False,
            'error': f"Erreur reseau: {str(e)}"
        }

    except MamouthAPIError as e:
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


def generate_texture_from_prompt(
    prompt: str,
    output_path: Path,
    resolution: str = "medium",
    api_key: Optional[str] = None
) -> Dict:
    """
    Genere une texture seamless a partir d'un prompt via Mamouth.ai
    """
    start_time = time.time()

    if not api_key:
        return {
            'success': False,
            'error': 'MAMOUTH_API_KEY manquante - Verifiez votre fichier .env'
        }

    if resolution not in RESOLUTION_PARAMS:
        return {
            'success': False,
            'error': f"Resolution invalide: {resolution}. Utilisez 'low', 'medium', ou 'high'"
        }

    if not prompt or len(prompt.strip()) == 0:
        return {
            'success': False,
            'error': 'Le prompt ne peut pas etre vide'
        }

    if len(prompt) > 1000:
        return {
            'success': False,
            'error': 'Le prompt est trop long (max 1000 caracteres)'
        }

    print(f"\n[MAMOUTH-TEXTURE] Generating texture from prompt")
    print(f"  Resolution: {resolution} ({RESOLUTION_PARAMS[resolution]}px)")

    try:
        texture_prompt = f"Generate an image of a seamless tileable texture of {prompt}. Top-down flat view, uniform lighting, no perspective, no 3D objects, suitable for repeating tile pattern."
        image_bytes = _call_mamouth_api(
            prompt=texture_prompt,
            model=DEFAULT_MODEL,
            api_key=api_key
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)

        img = Image.open(output_path)
        img_width, img_height = img.size

        generation_time = (time.time() - start_time) * 1000

        print(f"  [OK] Texture generated successfully")
        print(f"    Size: {img_width}x{img_height}")
        print(f"    Total time: {generation_time:.0f}ms")

        return {
            'success': True,
            'output_file': str(output_path),
            'output_filename': output_path.name,
            'prompt': prompt,
            'resolution': resolution,
            'image_width': img_width,
            'image_height': img_height,
            'generation_time_ms': round(generation_time, 2),
            'method': 'mamouth_texture'
        }

    except httpx.TimeoutException:
        return {
            'success': False,
            'error': "Timeout: L'API Mamouth n'a pas repondu en 2 minutes"
        }

    except httpx.NetworkError as e:
        return {
            'success': False,
            'error': f"Erreur reseau: {str(e)}"
        }

    except MamouthAPIError as e:
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


def infer_physics_from_prompt(prompt: str, api_key: str) -> Dict:
    """
    Infere les proprietes physiques d'un materiau via LLM (text-only, cheap).
    Retourne { mass, restitution, damping } ou des valeurs par defaut si echec.
    """
    import json

    DEFAULTS = {'mass': 1.0, 'restitution': 0.3, 'damping': 0.5}

    if not api_key:
        return DEFAULTS

    system_prompt = (
        "You are a physics material expert. Given a material name, return ONLY a JSON object with these 3 properties:\n"
        "- mass: relative density (0.1 = very light like foam, 1.0 = normal like wood, 5.0 = heavy like steel, 10.0 = very heavy like lead)\n"
        "- restitution: bounciness (0.0 = no bounce like clay, 0.5 = moderate like wood, 0.85 = bouncy like rubber, 1.0 = perfectly bouncy)\n"
        "- damping: energy absorption (0.0 = no damping like ice, 0.3 = low like metal, 0.6 = moderate like wood, 0.9 = high like foam)\n\n"
        'Return ONLY valid JSON, no explanation. Example: {"mass": 1.5, "restitution": 0.3, "damping": 0.6}'
    )

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': PHYSICS_MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'Material: {prompt}'}
        ]
    }

    print(f"  [MAMOUTH-PHYSICS] Inferring physics for: {prompt}")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(MAMOUTH_API_URL, json=payload, headers=headers)

        if response.status_code != 200:
            print(f"  [MAMOUTH-PHYSICS] API error {response.status_code}, using defaults")
            return DEFAULTS

        data = response.json()
        content = data['choices'][0]['message']['content'].strip()

        # Extraire le JSON du contenu (parfois entoure de ```json ... ```)
        if '```' in content:
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()

        physics = json.loads(content)

        result = {
            'mass': max(0.1, min(10.0, float(physics.get('mass', 1.0)))),
            'restitution': max(0.0, min(1.0, float(physics.get('restitution', 0.3)))),
            'damping': max(0.0, min(1.0, float(physics.get('damping', 0.5))))
        }

        print(f"  [OK] Physics inferred: mass={result['mass']}, restitution={result['restitution']}, damping={result['damping']}")
        return result

    except Exception as e:
        print(f"  [MAMOUTH-PHYSICS] Error: {e}, using defaults")
        return DEFAULTS

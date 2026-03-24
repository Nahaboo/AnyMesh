"""
Google AI image generation client.
- Images: Imagen 4 Fast via generativelanguage.googleapis.com
- Physics inference: Gemini 2.5 Flash via OpenAI-compatible endpoint
"""

import json
import time
import base64
from pathlib import Path
from typing import Dict, Optional
import httpx
from PIL import Image


IMAGEN_URL = "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-fast-generate-001:predict"
GEMINI_CHAT_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
PHYSICS_MODEL = "gemini-2.5-flash"


class GeminiAPIError(Exception):
    """Raised when a Google API call returns an error."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Gemini API Error {status_code}: {message}")


def _translate_error(status_code: int, api_message: str) -> str:
    ERROR_MESSAGES = {
        400: "Invalid prompt or rejected by content filter",
        401: "Invalid API key - check GEMINI_API_KEY in .env",
        403: "API key does not have access to Imagen - check your Google AI Studio plan",
        429: "Rate limit reached - retry in a few seconds",
        500: "Google API server error - retry later",
        503: "Google API service temporarily unavailable"
    }
    user_message = ERROR_MESSAGES.get(status_code, f"API error ({status_code})")
    return f"{user_message} | Details: {api_message}"


def _generate_imagen(prompt: str, api_key: str) -> bytes:
    """
    Call Imagen 4 Fast. Returns raw PNG bytes.
    Aspect ratio is always 1:1 (object isolation for 3D generation).
    """
    print("  [IMAGEN] Calling Imagen 4 Fast")
    print(f"    Prompt: {prompt[:100]}...")

    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "1:1",
            "personGeneration": "allow_adult",
        }
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            IMAGEN_URL,
            params={"key": api_key},
            json=payload
        )

    if response.status_code == 200:
        data = response.json()
        predictions = data.get("predictions", [])
        if not predictions:
            extra = data.get("error") or data.get("filters") or data.get("safetyAttributes") or data
            print(f"  [IMAGEN] Empty predictions. Full response: {extra}")
            raise GeminiAPIError(500, f"No predictions in Imagen response | Details: {extra}")

        image_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])
        print(f"  [OK] Image received: {len(image_bytes) / 1024:.1f} KB")
        return image_bytes

    try:
        error_json = response.json()
        error_message = error_json.get("error", {}).get("message", response.text)
    except Exception:
        error_message = response.text

    raise GeminiAPIError(status_code=response.status_code, message=error_message)


def generate_image_from_prompt(
    prompt: str,
    output_path: Path,
    resolution: str = "medium",
    api_key: Optional[str] = None
) -> Dict:
    """Generate an image from a text prompt via Imagen 4 Fast and save it as PNG."""
    start_time = time.time()

    if not api_key:
        return {
            'success': False,
            'error': 'GEMINI_API_KEY missing - check your .env file'
        }

    if not prompt or len(prompt.strip()) == 0:
        return {'success': False, 'error': 'Prompt cannot be empty'}

    if len(prompt) > 480:
        return {'success': False, 'error': 'Prompt too long (Imagen 4 limit: 480 characters)'}

    print("\n[IMAGEN-IMAGE] Generating image from prompt")

    try:
        full_prompt = f"{prompt.strip()}. Plain white background, subject centered and isolated, no environment, no shadows."
        image_bytes = _generate_imagen(prompt=full_prompt, api_key=api_key)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)

        img = Image.open(output_path)
        img_width, img_height = img.size
        generation_time = (time.time() - start_time) * 1000

        print(f"  [OK] Image generated: {img_width}x{img_height}, {generation_time:.0f}ms")

        return {
            'success': True,
            'output_file': str(output_path),
            'output_filename': output_path.name,
            'prompt': prompt,
            'resolution': resolution,
            'image_width': img_width,
            'image_height': img_height,
            'generation_time_ms': round(generation_time, 2),
            'method': 'imagen4_fast'
        }

    except httpx.TimeoutException:
        return {'success': False, 'error': 'Timeout: Imagen API did not respond within 2 minutes'}
    except httpx.NetworkError as e:
        return {'success': False, 'error': f'Network error: {str(e)}'}
    except GeminiAPIError as e:
        return {'success': False, 'error': _translate_error(e.status_code, e.message)}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}', 'error_type': type(e).__name__}


def generate_texture_from_prompt(
    prompt: str,
    output_path: Path,
    resolution: str = "medium",
    api_key: Optional[str] = None
) -> Dict:
    """Generate a seamless tileable texture from a text prompt via Imagen 4 Fast."""
    start_time = time.time()

    if not api_key:
        return {'success': False, 'error': 'GEMINI_API_KEY missing - check your .env file'}

    if not prompt or len(prompt.strip()) == 0:
        return {'success': False, 'error': 'Prompt cannot be empty'}

    if len(prompt) > 400:
        return {'success': False, 'error': 'Prompt too long (max 400 characters for texture)'}

    print("\n[IMAGEN-TEXTURE] Generating texture from prompt")

    try:
        texture_prompt = f"Seamless tileable texture of {prompt.strip()}. Top-down flat view, uniform lighting, no perspective, no 3D objects, suitable for repeating tile pattern."
        print(f"  [IMAGEN-TEXTURE] Full prompt sent: {texture_prompt}")
        image_bytes = _generate_imagen(prompt=texture_prompt, api_key=api_key)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)

        img = Image.open(output_path)
        img_width, img_height = img.size
        generation_time = (time.time() - start_time) * 1000

        print(f"  [OK] Texture generated: {img_width}x{img_height}, {generation_time:.0f}ms")

        return {
            'success': True,
            'output_file': str(output_path),
            'output_filename': output_path.name,
            'prompt': prompt,
            'resolution': resolution,
            'image_width': img_width,
            'image_height': img_height,
            'generation_time_ms': round(generation_time, 2),
            'method': 'imagen4_fast_texture'
        }

    except httpx.TimeoutException:
        return {'success': False, 'error': 'Timeout: Imagen API did not respond within 2 minutes'}
    except httpx.NetworkError as e:
        return {'success': False, 'error': f'Network error: {str(e)}'}
    except GeminiAPIError as e:
        return {'success': False, 'error': _translate_error(e.status_code, e.message)}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}', 'error_type': type(e).__name__}


def infer_physics_from_prompt(prompt: str, api_key: str) -> Dict:
    """
    Infer physical properties of a material from its name via Gemini 2.5 Flash (text-only).
    Returns {mass, restitution, damping} or defaults on failure.
    Uses the OpenAI-compatible Gemini endpoint.
    """
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

    payload = {
        'model': PHYSICS_MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'Material: {prompt}'}
        ]
    }

    print(f"  [GEMINI-PHYSICS] Inferring physics for: {prompt}")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                GEMINI_CHAT_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload
            )

        if response.status_code != 200:
            print(f"  [GEMINI-PHYSICS] API error {response.status_code}, using defaults")
            return DEFAULTS

        data = response.json()
        content = data['choices'][0]['message']['content'].strip()

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

        print(f"  [OK] Physics: mass={result['mass']}, restitution={result['restitution']}, damping={result['damping']}")
        return result

    except Exception as e:
        print(f"  [GEMINI-PHYSICS] Error: {e}, using defaults")
        return DEFAULTS

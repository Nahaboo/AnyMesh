"""
Mamouth.ai text-to-image generation client.
Generates images from text prompts via the Mamouth.ai API (OpenAI-compatible).
"""

import json
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
    """Raised when the Mamouth API returns an error."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Mamouth API Error {status_code}: {message}")


def _translate_error(status_code: int, api_message: str) -> str:
    """Return a user-facing error message for the given API status code."""
    ERROR_MESSAGES = {
        400: "Invalid prompt or rejected by content filter",
        401: "Invalid API key - check MAMOUTH_API_KEY in .env",
        402: "Insufficient API credits - top up your Mamouth account",
        429: "Rate limit reached - retry in a few seconds",
        500: "Mamouth.ai server error - retry later",
        503: "Mamouth.ai service temporarily unavailable"
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
    Low-level Mamouth API call. Returns raw PNG bytes.

    Uses OpenAI-compatible chat completions. Images are returned as base64
    in choices[0].message.images[0].image_url.url.
    """
    print(f"  [MAMOUTH-API] Calling text-to-image API")
    print(f"    Model: {model}")
    print(f"    Prompt: {prompt[:100]}...")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

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

        try:
            message = data['choices'][0]['message']
            images = message.get('images', [])

            if not images:
                content = message.get('content', '')
                print(f"  [DEBUG] No images in response. Content: {content[:200]}")
                raise MamouthAPIError(500, "No image in API response")

            image_url = images[0]['image_url']['url']

            # Strip data:image/png;base64, prefix if present
            if ',' in image_url:
                image_data = image_url.split(',', 1)[1]
            else:
                image_data = image_url

            image_bytes = base64.b64decode(image_data)
            print(f"  [OK] Image received: {len(image_bytes) / 1024:.1f} KB")
            return image_bytes

        except (KeyError, IndexError) as e:
            raise MamouthAPIError(500, f"Unexpected response format: {e}")

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
    """Generate an image from a text prompt via Mamouth.ai and save it as PNG."""
    start_time = time.time()

    if not api_key:
        return {
            'success': False,
            'error': 'MAMOUTH_API_KEY missing - check your .env file'
        }

    if resolution not in RESOLUTION_PARAMS:
        return {
            'success': False,
            'error': f"Invalid resolution: {resolution}. Use 'low', 'medium', or 'high'"
        }

    if not prompt or len(prompt.strip()) == 0:
        return {
            'success': False,
            'error': 'Prompt cannot be empty'
        }

    if len(prompt) > 1000:
        return {
            'success': False,
            'error': 'Prompt too long (max 1000 characters)'
        }

    print(f"\n[MAMOUTH-IMAGE] Generating image from prompt")
    print(f"  Resolution: {resolution} ({RESOLUTION_PARAMS[resolution]}px)")

    try:
        image_bytes = _call_mamouth_api(
            prompt=prompt,
            model=DEFAULT_MODEL,
            api_key=api_key,
            suffix="Plain white background, subject centered and isolated, no environment, no shadows."
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)

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
            'error': "Timeout: Mamouth API did not respond within 2 minutes"
        }

    except httpx.NetworkError as e:
        return {
            'success': False,
            'error': f"Network error: {str(e)}"
        }

    except MamouthAPIError as e:
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


def generate_texture_from_prompt(
    prompt: str,
    output_path: Path,
    resolution: str = "medium",
    api_key: Optional[str] = None
) -> Dict:
    """Generate a seamless tileable texture from a text prompt via Mamouth.ai."""
    start_time = time.time()

    if not api_key:
        return {
            'success': False,
            'error': 'MAMOUTH_API_KEY missing - check your .env file'
        }

    if resolution not in RESOLUTION_PARAMS:
        return {
            'success': False,
            'error': f"Invalid resolution: {resolution}. Use 'low', 'medium', or 'high'"
        }

    if not prompt or len(prompt.strip()) == 0:
        return {
            'success': False,
            'error': 'Prompt cannot be empty'
        }

    if len(prompt) > 1000:
        return {
            'success': False,
            'error': 'Prompt too long (max 1000 characters)'
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
            'error': "Timeout: Mamouth API did not respond within 2 minutes"
        }

    except httpx.NetworkError as e:
        return {
            'success': False,
            'error': f"Network error: {str(e)}"
        }

    except MamouthAPIError as e:
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


def infer_physics_from_prompt(prompt: str, api_key: str) -> Dict:
    """
    Infer physical properties of a material from its name via LLM (text-only).
    Returns {mass, restitution, damping} or defaults on failure.
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

        # Strip ```json ... ``` wrapper if present
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

"""
Batch generation 3D - genere des meshes 3D a partir d'un dossier d'images.

Usage:
    python batch_generate.py images/                        # Unique3D local (Docker)
    python batch_generate.py --runpod images/               # Unique3D RunPod
    python batch_generate.py --trellis images/              # TRELLIS: 1 image = 1 mesh
    python batch_generate.py --trellis --multi images/     # TRELLIS: N images = 1 mesh (multi-view)

Mode local : le worker Docker doit etre lance avant:
    docker compose up unique3d-worker

Mode RunPod : configurer RUNPOD_ENDPOINT_ID et RUNPOD_API_KEY dans .env
Mode TRELLIS : configurer RUNPOD_TRELLIS_ENDPOINT_ID et RUNPOD_API_KEY dans .env
"""

import sys
import os
import io
import time
import shutil
import base64
import argparse
from pathlib import Path

import requests
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

WORKER_URL = "http://localhost:8001"
TIMEOUT = 1800  # 30 min par generation
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

DATA_DIR = Path("data")
INPUT_IMAGES = DATA_DIR / "input_images"
GENERATED_MESHES = DATA_DIR / "generated_meshes"

RUNPOD_POLL_INTERVAL = 10  # secondes entre chaque poll
MAX_IMAGE_SIZE = 1024  # TRELLIS réduit à 518px en interne, 1024 suffit


def encode_image_b64(image_path: Path, max_size: int = MAX_IMAGE_SIZE) -> str:
    """Encode une image en base64, redimensionnée si > max_size px."""
    img = Image.open(image_path)
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def collect_images(paths: list[str]) -> list[Path]:
    """Collecte les images depuis les arguments (fichiers ou dossiers)."""
    images = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for f in sorted(path.iterdir()):
                if f.suffix.lower() in SUPPORTED_EXTENSIONS:
                    images.append(f)
        elif path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            images.append(path)
        else:
            print(f"  [SKIP] {p} (pas une image supportee)")
    return images


# --- MODE LOCAL (Docker) ---

def check_worker() -> bool:
    """Verifie que le worker Docker est accessible."""
    try:
        r = requests.get(f"{WORKER_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def generate_one_local(image_path: Path, batch_dir: Path, index: int) -> dict:
    """Genere un mesh 3D via le worker Docker local."""
    dest = batch_dir / f"image_{index:03d}{image_path.suffix.lower()}"
    shutil.copy2(image_path, dest)

    output_name = f"{image_path.stem}_unique3d.glb"
    output_path = GENERATED_MESHES / output_name

    ws_input = f"/workspace/{dest.as_posix()}"
    ws_output = f"/workspace/{output_path.as_posix()}"

    start = time.time()
    try:
        r = requests.post(
            f"{WORKER_URL}/process",
            json={
                "image_path": ws_input,
                "output_path": ws_output,
                "resolution": "medium",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        result = r.json()
        elapsed = time.time() - start

        if result.get("success"):
            size_mb = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0
            return {"success": True, "time": elapsed, "size_mb": size_mb, "output": output_name}
        else:
            return {"success": False, "time": elapsed, "error": result.get("error", "unknown")}

    except requests.exceptions.Timeout:
        return {"success": False, "time": time.time() - start, "error": "timeout (30 min)"}
    except Exception as e:
        return {"success": False, "time": time.time() - start, "error": str(e)}


# --- MODE RUNPOD (GPU distant) ---

def generate_one_trellis(image_path: Path, endpoint_id: str, api_key: str,
                         extra_images: list[Path] = None) -> dict:
    """Genere un mesh 3D via RunPod TRELLIS (single ou multi-image)."""
    output_name = f"{image_path.stem}_trellis.glb"
    output_path = GENERATED_MESHES / output_name

    headers = {"Authorization": f"Bearer {api_key}"}

    # Build input payload (simplify 0.60 = keep 40% of faces, best quality/clean tradeoff)
    if extra_images:
        all_paths = [image_path] + extra_images
        images_b64 = [encode_image_b64(p) for p in all_paths]
        input_data = {
            "images_base64": images_b64,
            "texture_size": 1024,
            "simplify": 0.60,
        }
        print(f"    Multi-image: {len(all_paths)} images")
    else:
        img_b64 = encode_image_b64(image_path)
        input_data = {
            "image_base64": img_b64,
            "texture_size": 1024,
            "simplify": 0.60,
        }

    start = time.time()

    try:
        r = requests.post(
            f"https://api.runpod.ai/v2/{endpoint_id}/run",
            headers=headers,
            json={
                "input": input_data,
                "policy": {"executionTimeout": 600000},
            },
            timeout=60,
        )
        r.raise_for_status()
        job_data = r.json()
    except Exception as e:
        return {"success": False, "time": time.time() - start, "error": f"Submit failed: {e}"}

    job_id = job_data.get("id")
    if not job_id:
        return {"success": False, "time": time.time() - start, "error": f"No job_id: {job_data}"}

    print(f"    Job soumis: {job_id}")

    while True:
        time.sleep(RUNPOD_POLL_INTERVAL)
        elapsed = time.time() - start

        try:
            r = requests.get(
                f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}",
                headers=headers,
                timeout=15,
            )
            r.raise_for_status()
            status_data = r.json()
        except Exception as e:
            print(f"    Poll error: {e}, retry...")
            continue

        status = status_data.get("status")
        print(f"    [{elapsed:.0f}s] Status: {status}")

        if status == "COMPLETED":
            output = status_data.get("output", {})
            if output.get("success") and output.get("glb_base64"):
                glb_data = base64.b64decode(output["glb_base64"])
                GENERATED_MESHES.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(glb_data)
                size_mb = len(glb_data) / (1024 * 1024)
                return {"success": True, "time": elapsed, "size_mb": size_mb, "output": output_name}
            else:
                return {"success": False, "time": elapsed, "error": output.get("error", "unknown")}

        elif status == "FAILED":
            error = status_data.get("error", "unknown")
            return {"success": False, "time": elapsed, "error": f"RunPod FAILED: {error}"}

        elif elapsed > TIMEOUT:
            return {"success": False, "time": elapsed, "error": "timeout (30 min)"}


def generate_one_runpod(image_path: Path, endpoint_id: str, api_key: str) -> dict:
    """Genere un mesh 3D via RunPod Serverless."""
    output_name = f"{image_path.stem}_unique3d.glb"
    output_path = GENERATED_MESHES / output_name

    # Encoder l'image en base64
    img_b64 = base64.b64encode(image_path.read_bytes()).decode()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    start = time.time()

    # 1. Soumettre le job (async)
    try:
        r = requests.post(
            f"https://api.runpod.ai/v2/{endpoint_id}/run",
            headers=headers,
            json={
                "input": {"image_base64": img_b64},
                "policy": {"executionTimeout": 2100000},  # 35 min
            },
            timeout=30,
        )
        r.raise_for_status()
        job_data = r.json()
    except Exception as e:
        return {"success": False, "time": time.time() - start, "error": f"Submit failed: {e}"}

    job_id = job_data.get("id")
    if not job_id:
        return {"success": False, "time": time.time() - start, "error": f"No job_id: {job_data}"}

    print(f"    Job soumis: {job_id}")

    # 2. Polling jusqu'a completion
    while True:
        time.sleep(RUNPOD_POLL_INTERVAL)
        elapsed = time.time() - start

        try:
            r = requests.get(
                f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}",
                headers=headers,
                timeout=15,
            )
            r.raise_for_status()
            status_data = r.json()
        except Exception as e:
            print(f"    Poll error: {e}, retry...")
            continue

        status = status_data.get("status")
        print(f"    [{elapsed:.0f}s] Status: {status}")

        if status == "COMPLETED":
            output = status_data.get("output", {})
            if output.get("success") and output.get("glb_base64"):
                glb_data = base64.b64decode(output["glb_base64"])
                GENERATED_MESHES.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(glb_data)
                size_mb = len(glb_data) / (1024 * 1024)
                return {"success": True, "time": elapsed, "size_mb": size_mb, "output": output_name}
            else:
                return {"success": False, "time": elapsed, "error": output.get("error", "unknown")}

        elif status == "FAILED":
            error = status_data.get("error", "unknown")
            return {"success": False, "time": elapsed, "error": f"RunPod FAILED: {error}"}

        elif elapsed > TIMEOUT:
            return {"success": False, "time": elapsed, "error": "timeout (30 min)"}


def main():
    parser = argparse.ArgumentParser(description="Batch generation 3D")
    parser.add_argument("inputs", nargs="+", help="Images ou dossiers d'images")
    parser.add_argument("--runpod", action="store_true", help="Unique3D via RunPod GPU distant")
    parser.add_argument("--trellis", action="store_true", help="TRELLIS via RunPod GPU distant")
    parser.add_argument("--multi", action="store_true", help="Multi-image: toutes les images = 1 seul mesh (TRELLIS uniquement)")
    args = parser.parse_args()

    if args.multi and not args.trellis:
        print("ERREUR: --multi ne fonctionne qu'avec --trellis")
        sys.exit(1)

    # Collecter les images
    images = collect_images(args.inputs)
    if not images:
        print("Aucune image trouvee.")
        sys.exit(1)

    if args.trellis:
        provider = "TRELLIS"
        mode = "RunPod"
    elif args.runpod:
        provider = "Unique3D"
        mode = "RunPod"
    else:
        provider = "Unique3D"
        mode = "Local"

    print(f"== Batch {provider} ({mode}) : {len(images)} image(s) ==")
    for i, img in enumerate(images):
        print(f"  {i + 1}. {img.name}")

    if args.trellis:
        # --- Mode TRELLIS RunPod ---
        endpoint_id = os.getenv("RUNPOD_TRELLIS_ENDPOINT_ID")
        api_key = os.getenv("RUNPOD_API_KEY")
        if not endpoint_id or not api_key:
            print("\nERREUR: RUNPOD_TRELLIS_ENDPOINT_ID et RUNPOD_API_KEY doivent etre configures dans .env")
            sys.exit(1)
        print(f"\nEndpoint TRELLIS: {endpoint_id}")
    elif args.runpod:
        # --- Mode Unique3D RunPod ---
        endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
        api_key = os.getenv("RUNPOD_API_KEY")
        if not endpoint_id or not api_key:
            print("\nERREUR: RUNPOD_ENDPOINT_ID et RUNPOD_API_KEY doivent etre configures dans .env")
            sys.exit(1)
        print(f"\nEndpoint RunPod: {endpoint_id}")
    else:
        # --- Mode local ---
        print("\nVerification du worker...", end=" ")
        if not check_worker():
            print("ECHEC")
            print("Le worker n'est pas accessible sur", WORKER_URL)
            print("Lancez-le avec : docker compose up unique3d-worker")
            sys.exit(1)
        print("OK")

    # Preparer le dossier batch (mode local seulement)
    batch_dir = None
    if not args.runpod and not args.trellis:
        batch_id = f"batch_{int(time.time())}"
        batch_dir = INPUT_IMAGES / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
    GENERATED_MESHES.mkdir(parents=True, exist_ok=True)

    # Generer sequentiellement
    results = []
    total_start = time.time()

    # Mode multi-image: toutes les images en un seul job
    if args.multi:
        print(f"\n[MULTI] {len(images)} images -> 1 mesh...")
        result = generate_one_trellis(images[0], endpoint_id, api_key, extra_images=images[1:])
        results.append(result)
        if result["success"]:
            print(f"  OK - {result['output']} ({result['size_mb']:.1f} Mo, {result['time']:.0f}s)")
        else:
            print(f"  ECHEC - {result['error']} ({result['time']:.0f}s)")

    for i, img in enumerate(images):
        if args.multi:
            break
        print(f"\n[{i + 1}/{len(images)}] {img.name}...")

        if args.trellis:
            result = generate_one_trellis(img, endpoint_id, api_key)
        elif args.runpod:
            result = generate_one_runpod(img, endpoint_id, api_key)
        else:
            result = generate_one_local(img, batch_dir, i)

        results.append(result)

        if result["success"]:
            print(f"  OK - {result['output']} ({result['size_mb']:.1f} Mo, {result['time']:.0f}s)")
        else:
            print(f"  ECHEC - {result['error']} ({result['time']:.0f}s)")

    # Resume
    total_time = time.time() - total_start
    ok = sum(1 for r in results if r["success"])
    fail = len(results) - ok

    print(f"\n== Resume ==")
    print(f"  Reussis : {ok}/{len(results)}")
    if fail:
        print(f"  Echoues : {fail}")
    print(f"  Temps total : {total_time / 60:.1f} min")
    print(f"  Sortie : {GENERATED_MESHES}/")


if __name__ == "__main__":
    main()

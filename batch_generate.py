"""
Batch 3D generation from a folder of images.

Usage:
    python batch_generate.py images/                       # Unique3D local (Docker)
    python batch_generate.py --runpod images/              # Unique3D RunPod
    python batch_generate.py --trellis images/             # TRELLIS v1: 1 image = 1 mesh
    python batch_generate.py --trellis --multi images/     # TRELLIS v1: N images = 1 mesh (multi-view)
    python batch_generate.py --trellis2 images/            # TRELLIS.2: 1 image = 1 mesh

Local mode: start the Docker worker first:
    docker compose up unique3d-worker

RunPod mode: set RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY in .env
TRELLIS mode: set RUNPOD_TRELLIS_ENDPOINT_ID and RUNPOD_API_KEY in .env
TRELLIS.2 mode: set RUNPOD_TRELLIS2_ENDPOINT_ID and RUNPOD_API_KEY in .env
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
TIMEOUT = 1800  # 30 min per generation
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

DATA_DIR = Path("data")
INPUT_IMAGES = DATA_DIR / "input_images"
GENERATED_MESHES = DATA_DIR / "generated_meshes"

RUNPOD_POLL_INTERVAL = 10  # seconds between polls
MAX_IMAGE_SIZE = 1024  # TRELLIS internally reduces to 518px; 1024 is sufficient


def encode_image_b64(image_path: Path, max_size: int = MAX_IMAGE_SIZE, remove_bg: bool = False) -> str:
    """Encode an image as base64, resizing it if larger than max_size px.
    If remove_bg=True, runs rembg background removal before encoding."""
    img = Image.open(image_path).convert("RGBA")
    if remove_bg:
        try:
            from rembg import remove as rembg_remove
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            result = rembg_remove(buf.getvalue())
            img = Image.open(io.BytesIO(result)).convert("RGBA")
            print(f"    [rembg] background removed")
        except Exception as e:
            print(f"    [rembg] failed: {e} — sending original")
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def collect_images(paths: list[str]) -> list[Path]:
    """Collect images from the given arguments (files or directories)."""
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
            print(f"  [SKIP] {p} (unsupported format)")
    return images


# --- MODE LOCAL (Docker) ---

def check_worker() -> bool:
    """Check that the Docker worker is reachable."""
    try:
        r = requests.get(f"{WORKER_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def generate_one_local(image_path: Path, batch_dir: Path, index: int) -> dict:
    """Generate a 3D mesh via the local Docker worker."""
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
    """Generate a 3D mesh via RunPod TRELLIS (single or multi-image)."""
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

    print(f"    Job: {job_id}")

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


def generate_one_trellis2(image_path: Path, endpoint_id: str, api_key: str, remove_bg: bool = False) -> dict:
    """Generate a 3D mesh via RunPod TRELLIS.2 (returns glb_url, not glb_base64)."""
    output_name = f"{image_path.stem}_trellis2.glb"
    output_path = GENERATED_MESHES / output_name

    img_b64 = encode_image_b64(image_path, remove_bg=remove_bg)
    headers = {"Authorization": f"Bearer {api_key}"}
    input_data = {
        "image_base64": img_b64,
        "decimation_target": 500000,
        "texture_size": 2048,
    }

    start = time.time()

    try:
        r = requests.post(
            f"https://api.runpod.ai/v2/{endpoint_id}/run",
            headers=headers,
            json={"input": input_data, "policy": {"executionTimeout": 900000}},
            timeout=60,
        )
        r.raise_for_status()
        job_data = r.json()
    except Exception as e:
        return {"success": False, "time": time.time() - start, "error": f"Submit failed: {e}"}

    job_id = job_data.get("id")
    if not job_id:
        return {"success": False, "time": time.time() - start, "error": f"No job_id: {job_data}"}

    print(f"    Job: {job_id}")

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
            if output.get("success") and output.get("glb_url"):
                glb_url = output["glb_url"]
                r = requests.get(glb_url, timeout=60)
                r.raise_for_status()
                GENERATED_MESHES.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(r.content)
                size_mb = len(r.content) / (1024 * 1024)
                return {"success": True, "time": elapsed, "size_mb": size_mb, "output": output_name}
            else:
                return {"success": False, "time": elapsed, "error": output.get("error", "unknown")}

        elif status == "FAILED":
            error = status_data.get("error", "unknown")
            return {"success": False, "time": elapsed, "error": f"RunPod FAILED: {error}"}

        elif elapsed > TIMEOUT:
            return {"success": False, "time": elapsed, "error": "timeout (30 min)"}


def generate_one_runpod(image_path: Path, endpoint_id: str, api_key: str) -> dict:
    """Generate a 3D mesh via RunPod Serverless."""
    output_name = f"{image_path.stem}_unique3d.glb"
    output_path = GENERATED_MESHES / output_name

    img_b64 = base64.b64encode(image_path.read_bytes()).decode()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    start = time.time()

    # Submit async job
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

    print(f"    Job: {job_id}")

    # Poll until completion
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
    parser = argparse.ArgumentParser(description="Batch 3D generation")
    parser.add_argument("inputs", nargs="+", help="Images or image directories")
    parser.add_argument("--runpod", action="store_true", help="Unique3D via remote RunPod GPU")
    parser.add_argument("--trellis", action="store_true", help="TRELLIS v1 via remote RunPod GPU")
    parser.add_argument("--trellis2", action="store_true", help="TRELLIS.2 via remote RunPod GPU")
    parser.add_argument("--multi", action="store_true", help="Multi-image: all images = 1 mesh (TRELLIS v1 only)")
    parser.add_argument("--rembg", action="store_true", help="Remove background locally via rembg before sending")
    args = parser.parse_args()

    if args.multi and not args.trellis:
        print("ERROR: --multi only works with --trellis")
        sys.exit(1)

    if args.trellis and args.trellis2:
        print("ERROR: --trellis and --trellis2 are mutually exclusive")
        sys.exit(1)

    images = collect_images(args.inputs)
    if not images:
        print("No images found.")
        sys.exit(1)

    if args.trellis2:
        provider = "TRELLIS.2"
        mode = "RunPod"
    elif args.trellis:
        provider = "TRELLIS v1"
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

    if args.trellis2:
        # --- TRELLIS.2 RunPod mode ---
        endpoint_id = os.getenv("RUNPOD_TRELLIS2_ENDPOINT_ID")
        api_key = os.getenv("RUNPOD_API_KEY")
        if not endpoint_id or not api_key:
            print("\nERROR: RUNPOD_TRELLIS2_ENDPOINT_ID and RUNPOD_API_KEY must be set in .env")
            sys.exit(1)
        print(f"\nEndpoint TRELLIS.2: {endpoint_id}")
    elif args.trellis:
        # --- TRELLIS v1 RunPod mode ---
        endpoint_id = os.getenv("RUNPOD_TRELLIS_ENDPOINT_ID")
        api_key = os.getenv("RUNPOD_API_KEY")
        if not endpoint_id or not api_key:
            print("\nERROR: RUNPOD_TRELLIS_ENDPOINT_ID and RUNPOD_API_KEY must be set in .env")
            sys.exit(1)
        print(f"\nEndpoint TRELLIS v1: {endpoint_id}")
    elif args.runpod:
        # --- Unique3D RunPod mode ---
        endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
        api_key = os.getenv("RUNPOD_API_KEY")
        if not endpoint_id or not api_key:
            print("\nERROR: RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY must be set in .env")
            sys.exit(1)
        print(f"\nEndpoint RunPod: {endpoint_id}")
    else:
        # --- Local mode ---
        print("\nChecking worker...", end=" ")
        if not check_worker():
            print("FAIL")
            print("Worker not reachable at", WORKER_URL)
            print("Start it with: docker compose up unique3d-worker")
            sys.exit(1)
        print("OK")

    # Prepare batch directory (local mode only)
    batch_dir = None
    if not args.runpod and not args.trellis:
        batch_id = f"batch_{int(time.time())}"
        batch_dir = INPUT_IMAGES / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
    GENERATED_MESHES.mkdir(parents=True, exist_ok=True)

    results = []
    total_start = time.time()

    # Multi-image: all images in a single job
    if args.multi:
        print(f"\n[MULTI] {len(images)} images -> 1 mesh...")
        result = generate_one_trellis(images[0], endpoint_id, api_key, extra_images=images[1:])
        results.append(result)
        if result["success"]:
            print(f"  OK - {result['output']} ({result['size_mb']:.1f} MB, {result['time']:.0f}s)")
        else:
            print(f"  FAIL - {result['error']} ({result['time']:.0f}s)")

    for i, img in enumerate(images):
        if args.multi:
            break
        print(f"\n[{i + 1}/{len(images)}] {img.name}...")

        if args.trellis2:
            result = generate_one_trellis2(img, endpoint_id, api_key, remove_bg=args.rembg)
        elif args.trellis:
            result = generate_one_trellis(img, endpoint_id, api_key)
        elif args.runpod:
            result = generate_one_runpod(img, endpoint_id, api_key)
        else:
            result = generate_one_local(img, batch_dir, i)

        results.append(result)

        if result["success"]:
            print(f"  OK - {result['output']} ({result['size_mb']:.1f} MB, {result['time']:.0f}s)")
        else:
            print(f"  FAIL - {result['error']} ({result['time']:.0f}s)")

    total_time = time.time() - total_start
    ok = sum(1 for r in results if r["success"])
    fail = len(results) - ok

    print(f"\n== Summary ==")
    print(f"  Success: {ok}/{len(results)}")
    if fail:
        print(f"  Failed: {fail}")
    print(f"  Total time: {total_time / 60:.1f} min")
    print(f"  Output: {GENERATED_MESHES}/")


if __name__ == "__main__":
    main()

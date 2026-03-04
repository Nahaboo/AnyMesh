"""
Benchmark providers 3D - compare TRELLIS, TripoSR, Stability AI et Unique3D
sur les memes images.

Usage:
    python benchmark_providers.py image.png
    python benchmark_providers.py images/
    python benchmark_providers.py img1.png img2.jpg --resolution high

    # Selectionner les providers a tester
    python benchmark_providers.py image.png --only trellis stability
    python benchmark_providers.py image.png --skip triposr unique3d

Prerequis par provider:
    TRELLIS    : RUNPOD_TRELLIS_ENDPOINT_ID + RUNPOD_API_KEY dans .env
    TripoSR    : pip install -r tools/TripoSR/requirements.txt
    Stability  : STABILITY_API_KEY dans .env
    Unique3D   : worker Docker lance (docker compose up unique3d-worker)

Sortie:
    data/generated_meshes/<stem>_trellis.glb
    data/generated_meshes/<stem>_triposr.glb
    data/generated_meshes/<stem>_stability.glb
    data/generated_meshes/<stem>_unique3d.glb
    benchmark_results.txt
"""

import sys
import os
import io
import time
import base64
import argparse
from pathlib import Path

import requests
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
GENERATED_MESHES = Path("data/generated_meshes")
RUNPOD_POLL_INTERVAL = 10
TIMEOUT = 1800
MAX_IMAGE_SIZE = 1024

ALL_PROVIDERS = ["trellis", "triposr", "stability", "unique3d"]


# ─── Helpers ────────────────────────────────────────────────────────────────

def collect_images(paths: list[str]) -> list[Path]:
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
            print(f"  [SKIP] {p}")
    return images


def encode_image_b64(image_path: Path, max_size: int = MAX_IMAGE_SIZE) -> str:
    img = Image.open(image_path)
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def mesh_quality_stats(glb_path: Path) -> dict:
    """Calcule les stats qualite d'un GLB : faces, watertight, composantes, aspect ratio, texture."""
    try:
        import trimesh
        import numpy as np
        loaded = trimesh.load(str(glb_path), force="scene")

        # Fusionner toutes les geometries en un seul mesh pour les stats globales
        if hasattr(loaded, "geometry"):
            meshes = list(loaded.geometry.values())
        else:
            meshes = [loaded]

        faces = sum(len(m.faces) for m in meshes)
        components = len(meshes)

        # Watertight = toutes les geometries sont watertight
        watertight = all(m.is_watertight for m in meshes)

        # Aspect ratio moyen : rapport entre le plus long et le plus court cote de chaque triangle
        all_aspect = []
        for m in meshes:
            if len(m.faces) == 0:
                continue
            v = m.vertices[m.faces]          # (F, 3, 3)
            e0 = np.linalg.norm(v[:, 1] - v[:, 0], axis=1)
            e1 = np.linalg.norm(v[:, 2] - v[:, 1], axis=1)
            e2 = np.linalg.norm(v[:, 0] - v[:, 2], axis=1)
            sides = np.stack([e0, e1, e2], axis=1)
            ratio = sides.max(axis=1) / (sides.min(axis=1) + 1e-10)
            all_aspect.extend(ratio.tolist())
        aspect_ratio = float(np.mean(all_aspect)) if all_aspect else 0.0

        # Texture : chercher baseColorTexture dans les materiaux
        tex_res = None
        for m in meshes:
            if hasattr(m, "visual") and hasattr(m.visual, "material"):
                mat = m.visual.material
                tex = getattr(mat, "baseColorTexture", None)
                if tex is not None:
                    tex_res = f"{tex.width}x{tex.height}"
                    break

        return {
            "faces": faces,
            "components": components,
            "watertight": watertight,
            "aspect_ratio": round(aspect_ratio, 2),
            "texture": tex_res or "---",
        }
    except Exception as e:
        return {"faces": 0, "components": 0, "watertight": False, "aspect_ratio": 0.0, "texture": "---"}


def skipped() -> dict:
    return {"success": False, "time": 0, "error": "skipped"}


# ─── TRELLIS (RunPod) ────────────────────────────────────────────────────────

def run_trellis(image_path: Path, endpoint_id: str, api_key: str) -> dict:
    output_path = GENERATED_MESHES / f"{image_path.stem}_trellis.glb"
    headers = {"Authorization": f"Bearer {api_key}"}
    img_b64 = encode_image_b64(image_path)
    start = time.time()

    try:
        r = requests.post(
            f"https://api.runpod.ai/v2/{endpoint_id}/run",
            headers=headers,
            json={
                "input": {"image_base64": img_b64, "texture_size": 1024, "simplify": 0.60},
                "policy": {"executionTimeout": 600000},
            },
            timeout=60,
        )
        r.raise_for_status()
        job_id = r.json().get("id")
    except Exception as e:
        return {"success": False, "time": time.time() - start, "error": str(e)}

    if not job_id:
        return {"success": False, "time": time.time() - start, "error": "No job_id"}

    print(f"    Job: {job_id}")

    while True:
        time.sleep(RUNPOD_POLL_INTERVAL)
        elapsed = time.time() - start
        try:
            r = requests.get(
                f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}",
                headers=headers, timeout=15,
            )
            status_data = r.json()
        except Exception as e:
            print(f"    Poll error: {e}")
            continue

        status = status_data.get("status")
        print(f"    [{elapsed:.0f}s] {status}")

        if status == "COMPLETED":
            output = status_data.get("output", {})
            if output.get("success") and output.get("glb_base64"):
                glb_data = base64.b64decode(output["glb_base64"])
                output_path.write_bytes(glb_data)
                stats = mesh_quality_stats(output_path)
                return {
                    "success": True, "time": elapsed,
                    "size_mb": len(glb_data) / (1024 * 1024),
                    "output": output_path.name,
                    **stats,
                }
            return {"success": False, "time": elapsed, "error": output.get("error", "unknown")}
        elif status == "FAILED":
            return {"success": False, "time": elapsed, "error": "RunPod FAILED"}
        elif elapsed > TIMEOUT:
            return {"success": False, "time": elapsed, "error": "timeout"}


# ─── TripoSR (local GPU) ─────────────────────────────────────────────────────

def run_triposr(image_path: Path, resolution: str) -> dict:
    output_path = GENERATED_MESHES / f"{image_path.stem}_triposr.glb"
    start = time.time()
    try:
        from src.triposr_client import generate_mesh_from_image_triposr
        result = generate_mesh_from_image_triposr(
            image_path=image_path, output_path=output_path, resolution=resolution,
        )
    except ImportError as e:
        return {"success": False, "time": time.time() - start, "error": f"Import: {e}"}

    elapsed = time.time() - start
    if result.get("success") and output_path.exists():
        stats = mesh_quality_stats(output_path)
        return {
            "success": True, "time": elapsed,
            "size_mb": output_path.stat().st_size / (1024 * 1024),
            "output": output_path.name,
            **stats,
        }
    return {"success": False, "time": elapsed, "error": result.get("error", "unknown")}


# ─── Stability AI (SF3D cloud) ───────────────────────────────────────────────

def run_stability(image_path: Path, resolution: str) -> dict:
    output_path = GENERATED_MESHES / f"{image_path.stem}_stability.glb"
    start = time.time()
    try:
        from src.stability_client import generate_mesh_from_image_sf3d
        result = generate_mesh_from_image_sf3d(
            image_path=image_path, output_path=output_path, resolution=resolution,
        )
    except ImportError as e:
        return {"success": False, "time": time.time() - start, "error": f"Import: {e}"}

    elapsed = time.time() - start
    if result.get("success") and output_path.exists():
        stats = mesh_quality_stats(output_path)
        return {
            "success": True, "time": elapsed,
            "size_mb": output_path.stat().st_size / (1024 * 1024),
            "output": output_path.name,
            **stats,
        }
    return {"success": False, "time": elapsed, "error": result.get("error", "unknown")}


# ─── Unique3D (Docker worker local) ─────────────────────────────────────────

def run_unique3d(image_path: Path, resolution: str) -> dict:
    output_path = GENERATED_MESHES / f"{image_path.stem}_unique3d.glb"
    start = time.time()
    try:
        from src.unique3d_client import generate_mesh_from_image_unique3d
        result = generate_mesh_from_image_unique3d(
            image_path=image_path, output_path=output_path, resolution=resolution,
        )
    except ImportError as e:
        return {"success": False, "time": time.time() - start, "error": f"Import: {e}"}

    elapsed = time.time() - start
    if result.get("success") and output_path.exists():
        stats = mesh_quality_stats(output_path)
        return {
            "success": True, "time": elapsed,
            "size_mb": output_path.stat().st_size / (1024 * 1024),
            "output": output_path.name,
            **stats,
        }
    return {"success": False, "time": elapsed, "error": result.get("error", "unknown")}


# ─── Affichage ───────────────────────────────────────────────────────────────

PROVIDER_LABELS = {
    "trellis": "TRELLIS",
    "triposr": "TripoSR",
    "stability": "Stability",
    "unique3d": "Unique3D",
}


def print_comparison(image_name: str, results: dict[str, dict]):
    header = f"  {'Provider':<12} {'Statut':<8} {'Temps':>7} {'Taille':>8} {'Faces':>8} {'Compos.':>8} {'Watertight':<12} {'AspRatio':>9} {'Texture':>12}"
    sep    = f"  {'-'*12} {'-'*8} {'-'*7} {'-'*8} {'-'*8} {'-'*8} {'-'*12} {'-'*9} {'-'*12}"
    print(f"\n{header}")
    print(sep)
    for provider, r in results.items():
        label = PROVIDER_LABELS[provider]
        if r.get("error") == "skipped":
            print(f"  {label:<12} {'---':<8}")
        elif r["success"]:
            wt = "Oui" if r["watertight"] else "Non"
            print(
                f"  {label:<12} {'OK':<8} {r['time']:>6.0f}s {r['size_mb']:>7.1f}M"
                f" {r['faces']:>8,} {r['components']:>8} {wt:<12} {r['aspect_ratio']:>9.2f} {r['texture']:>12}"
            )
        else:
            print(f"  {label:<12} {'ECHEC':<8}  {r['error']}")


def save_results(results: list[dict], active_providers: list[str], output_file: Path):
    lines = ["Benchmark 3D Providers", "=" * 50, f"Providers: {', '.join(active_providers)}", ""]
    for item in results:
        lines.append(f"Image: {item['image']}")
        for provider in active_providers:
            r = item[provider]
            label = PROVIDER_LABELS[provider]
            if r.get("error") == "skipped":
                lines.append(f"  {label}: ---")
            elif r["success"]:
                wt = "watertight" if r["watertight"] else "non-watertight"
                lines.append(
                    f"  {label}: OK | {r['time']:.0f}s | {r['size_mb']:.1f}MB"
                    f" | {r['faces']:,} faces | {r['components']} compos. | {wt}"
                    f" | aspect {r['aspect_ratio']:.2f} | texture {r['texture']} | {r['output']}"
                )
            else:
                lines.append(f"  {label}: ECHEC | {r['error']}")
        lines.append("")
    output_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nResultats sauvegardes: {output_file}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Benchmark 4 providers 3D generation")
    parser.add_argument("inputs", nargs="+", help="Images ou dossiers")
    parser.add_argument("--resolution", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--only", nargs="+", choices=ALL_PROVIDERS, metavar="PROVIDER",
                        help="Tester seulement ces providers")
    parser.add_argument("--skip", nargs="+", choices=ALL_PROVIDERS, metavar="PROVIDER",
                        help="Ignorer ces providers")
    args = parser.parse_args()

    # Determiner les providers actifs
    if args.only:
        active = args.only
    elif args.skip:
        active = [p for p in ALL_PROVIDERS if p not in args.skip]
    else:
        active = list(ALL_PROVIDERS)

    images = collect_images(args.inputs)
    if not images:
        print("Aucune image trouvee.")
        sys.exit(1)

    # Verifier les prerequis
    trellis_endpoint = os.getenv("RUNPOD_TRELLIS_ENDPOINT_ID")
    trellis_key = os.getenv("RUNPOD_API_KEY")
    stability_key = os.getenv("STABILITY_API_KEY")

    errors = []
    if "trellis" in active and (not trellis_endpoint or not trellis_key):
        errors.append("TRELLIS: RUNPOD_TRELLIS_ENDPOINT_ID et RUNPOD_API_KEY manquants dans .env")
    if "stability" in active and not stability_key:
        errors.append("Stability: STABILITY_API_KEY manquant dans .env")

    if errors:
        for e in errors:
            print(f"ERREUR: {e}")
        print("Utilisez --skip ou --only pour exclure les providers non configures.")
        sys.exit(1)

    # Precharger TripoSR (lourd a importer)
    if "triposr" in active:
        print("Chargement TripoSR...", end=" ", flush=True)
        try:
            from src.triposr_client import generate_mesh_from_image_triposr
            print("OK")
        except ImportError as e:
            print(f"ECHEC: {e}")
            print("Retirez triposr avec --skip triposr ou installez les dependances.")
            sys.exit(1)

    GENERATED_MESHES.mkdir(parents=True, exist_ok=True)

    print(f"\n== Benchmark [{', '.join(active)}] | {len(images)} image(s) | resolution={args.resolution} ==")

    all_results = []

    for i, img in enumerate(images):
        print(f"\n[{i + 1}/{len(images)}] {img.name}")
        row = {"image": img.name}

        for provider in ALL_PROVIDERS:
            if provider not in active:
                row[provider] = skipped()
                continue

            print(f"  [{PROVIDER_LABELS[provider]}]...")

            if provider == "trellis":
                row[provider] = run_trellis(img, trellis_endpoint, trellis_key)
            elif provider == "triposr":
                row[provider] = run_triposr(img, args.resolution)
            elif provider == "stability":
                row[provider] = run_stability(img, args.resolution)
            elif provider == "unique3d":
                row[provider] = run_unique3d(img, args.resolution)

        print_comparison(img.name, {p: row[p] for p in ALL_PROVIDERS})
        all_results.append(row)

    save_results(all_results, active, Path("benchmark_results.txt"))


if __name__ == "__main__":
    main()

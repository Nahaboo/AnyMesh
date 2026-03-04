"""
Batch generation TripoSR - genere des meshes 3D a partir d'un dossier d'images.
Tourne en local sur le GPU (pas de Docker requis).

Usage:
    python batch_triposr.py images/              # Toutes les images d'un dossier
    python batch_triposr.py img1.png img2.jpg    # Fichiers specifiques

Prerequis:
    pip install -r tools/TripoSR/requirements.txt
"""

import sys
import time
import argparse
from pathlib import Path

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
GENERATED_MESHES = Path("data/generated_meshes")


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


def main():
    parser = argparse.ArgumentParser(description="Batch generation 3D avec TripoSR (local)")
    parser.add_argument("inputs", nargs="+", help="Images ou dossiers d'images")
    parser.add_argument("--resolution", choices=["low", "medium", "high"], default="medium",
                        help="Resolution marching cubes (default: medium)")
    args = parser.parse_args()

    # Collecter les images
    images = collect_images(args.inputs)
    if not images:
        print("Aucune image trouvee.")
        sys.exit(1)

    print(f"== Batch TripoSR : {len(images)} image(s), resolution={args.resolution} ==")
    for i, img in enumerate(images):
        print(f"  {i + 1}. {img.name}")

    # Import du client (charge torch, verifie GPU)
    print("\nChargement de TripoSR...", end=" ", flush=True)
    try:
        from src.triposr_client import generate_mesh_from_image_triposr
        print("OK")
    except ImportError as e:
        print("ECHEC")
        print(f"Erreur: {e}")
        print("Installez les dependances: pip install -r tools/TripoSR/requirements.txt")
        sys.exit(1)

    GENERATED_MESHES.mkdir(parents=True, exist_ok=True)

    # Generer sequentiellement
    results = []
    total_start = time.time()

    for i, img in enumerate(images):
        print(f"\n[{i + 1}/{len(images)}] {img.name}...")
        output_path = GENERATED_MESHES / f"{img.stem}_triposr.glb"

        result = generate_mesh_from_image_triposr(
            image_path=img,
            output_path=output_path,
            resolution=args.resolution,
        )
        results.append(result)

        elapsed = result.get("generation_time_ms", 0) / 1000
        if result["success"]:
            size_mb = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0
            print(f"  OK - {output_path.name} ({size_mb:.1f} Mo, {elapsed:.0f}s)")
        else:
            print(f"  ECHEC - {result.get('error', 'unknown')} ({elapsed:.0f}s)")

    # Resume
    total_time = time.time() - total_start
    ok = sum(1 for r in results if r["success"])
    fail = len(results) - ok

    print("\n== Resume ==")
    print(f"  Reussis : {ok}/{len(results)}")
    if fail:
        print(f"  Echoues : {fail}")
    print(f"  Temps total : {total_time / 60:.1f} min")
    print(f"  Sortie : {GENERATED_MESHES}/")


if __name__ == "__main__":
    main()

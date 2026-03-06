"""
Batch 3D generation with TripoSR. Runs locally on GPU, no Docker required.

Usage:
    python batch_triposr.py images/              # All images in a directory
    python batch_triposr.py img1.png img2.jpg    # Specific files

Prerequisites:
    pip install -r tools/TripoSR/requirements.txt
"""

import sys
import time
import argparse
from pathlib import Path

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
GENERATED_MESHES = Path("data/generated_meshes")


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


def main():
    parser = argparse.ArgumentParser(description="Batch 3D generation with TripoSR (local)")
    parser.add_argument("inputs", nargs="+", help="Images or image directories")
    parser.add_argument("--resolution", choices=["low", "medium", "high"], default="medium",
                        help="Marching cubes resolution (default: medium)")
    args = parser.parse_args()

    images = collect_images(args.inputs)
    if not images:
        print("No images found.")
        sys.exit(1)

    print(f"== Batch TripoSR: {len(images)} image(s), resolution={args.resolution} ==")
    for i, img in enumerate(images):
        print(f"  {i + 1}. {img.name}")

    print("\nLoading TripoSR...", end=" ", flush=True)
    try:
        from src.triposr_client import generate_mesh_from_image_triposr
        print("OK")
    except ImportError as e:
        print("FAIL")
        print(f"Error: {e}")
        print("Install dependencies: pip install -r tools/TripoSR/requirements.txt")
        sys.exit(1)

    GENERATED_MESHES.mkdir(parents=True, exist_ok=True)

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
            print(f"  OK - {output_path.name} ({size_mb:.1f} MB, {elapsed:.0f}s)")
        else:
            print(f"  FAIL - {result.get('error', 'unknown')} ({elapsed:.0f}s)")

    total_time = time.time() - total_start
    ok = sum(1 for r in results if r["success"])
    fail = len(results) - ok

    print("\n== Summary ==")
    print(f"  Success: {ok}/{len(results)}")
    if fail:
        print(f"  Failed: {fail}")
    print(f"  Total time: {total_time / 60:.1f} min")
    print(f"  Output: {GENERATED_MESHES}/")


if __name__ == "__main__":
    main()

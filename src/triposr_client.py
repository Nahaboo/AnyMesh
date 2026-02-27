"""
Client local TripoSR pour generation de mesh 3D
Alternative gratuite a Stability AI Fast 3D

TripoSR est un modele open-source co-developpe par Tripo AI et Stability AI
qui genere des meshes 3D a partir d'une seule image en < 0.5 sec sur GPU.
"""

import sys
import time
import trimesh
from pathlib import Path
from typing import Dict

# Ajouter TripoSR au path Python
TRIPOSR_PATH = Path(__file__).parent.parent / "tools" / "TripoSR"
if str(TRIPOSR_PATH) not in sys.path:
    sys.path.insert(0, str(TRIPOSR_PATH))

# Cache global pour le modele (evite de le recharger a chaque appel)
_model_cache = None
_model_device = None


def _get_model(device: str):
    """Charge le modele TripoSR (cache apres premier appel)"""
    global _model_cache, _model_device

    if _model_cache is not None and _model_device == device:
        return _model_cache

    from tsr.system import TSR

    print(f"  [TRIPOSR] Loading model (first time, will be cached)...")
    model = TSR.from_pretrained(
        "stabilityai/TripoSR",
        config_name="config.yaml",
        weight_name="model.ckpt"
    )
    model.to(device)
    model.renderer.set_chunk_size(8192)

    _model_cache = model
    _model_device = device

    return model


def generate_mesh_from_image_triposr(
    image_path: Path,
    output_path: Path,
    resolution: str = "medium",
    foreground_ratio: float = 0.85
) -> Dict:
    """
    Genere un mesh 3D a partir d'une image avec TripoSR (local, gratuit)

    Args:
        image_path: Chemin vers l'image d'entree (JPG/PNG)
        output_path: Chemin de sortie (.glb)
        resolution: 'low', 'medium', 'high' (affecte marching cubes resolution)
        foreground_ratio: Ratio de l'objet dans l'image (0.5-1.0)

    Returns:
        Dict avec resultats de generation:
        {
            'success': bool,
            'output_file': str,
            'vertices_count': int,
            'faces_count': int,
            'resolution': str,
            'generation_time_ms': float,
            'method': 'triposr_local',
            'api_credits_used': 0
        }
    """
    start_time = time.time()

    # Mapping resolution -> marching cubes resolution
    MC_RESOLUTION = {
        'low': 128,
        'medium': 256,
        'high': 512
    }
    mc_res = MC_RESOLUTION.get(resolution, 256)

    try:
        # Imports lazy pour eviter chargement au demarrage du serveur
        from tsr.utils import remove_background, resize_foreground
        from PIL import Image
        import torch
        import numpy as np

        print(f"\n[TRIPOSR] Generating mesh from image")
        print(f"  Input: {image_path.name}")
        print(f"  Resolution: {resolution} (mc={mc_res})")

        # Detecter device
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"  Device: {device}")

        if device == "cpu":
            print("  [WARN] Running on CPU - this will be slow!")

        # Charger le modele (cache)
        model = _get_model(device)

        # Pretraitement de l'image (identique au pipeline officiel run.py)
        print(f"  Preprocessing image...")
        image = remove_background(Image.open(image_path), force=True)
        image = resize_foreground(image, foreground_ratio)
        # Fond gris 50% via alpha compositing (comme le pipeline officiel)
        image = np.array(image).astype(np.float32) / 255.0
        image = image[:, :, :3] * image[:, :, 3:4] + (1 - image[:, :, 3:4]) * 0.5
        image = Image.fromarray((image * 255.0).astype(np.uint8))

        # Generation
        print(f"  Generating 3D representation...")
        with torch.no_grad():
            scene_codes = model([image], device=device)

        # Extraction du mesh
        print(f"  Extracting mesh (resolution={mc_res})...")
        meshes = model.extract_mesh(
            scene_codes,
            has_vertex_color=True,
            resolution=mc_res,
            threshold=25.0
        )
        mesh = meshes[0]

        # GLB-First: Forcer extension .glb
        if output_path.suffix.lower() != '.glb':
            output_path = output_path.with_suffix('.glb')

        # Exporter en GLB
        print(f"  Exporting to GLB: {output_path.name}")
        mesh.export(str(output_path), file_type='glb')

        # Recharger pour stats (trimesh)
        final_mesh = trimesh.load(str(output_path))
        if hasattr(final_mesh, 'geometry'):
            meshes_list = list(final_mesh.geometry.values())
            if len(meshes_list) > 0:
                final_mesh = meshes_list[0] if len(meshes_list) == 1 else trimesh.util.concatenate(meshes_list)

        vertices_count = len(final_mesh.vertices)
        faces_count = len(final_mesh.faces)
        generation_time = (time.time() - start_time) * 1000

        print(f"  [OK] Mesh generated successfully")
        print(f"    Vertices: {vertices_count}")
        print(f"    Faces: {faces_count}")
        print(f"    Time: {generation_time:.2f}ms")

        return {
            'success': True,
            'output_file': str(output_path),
            'output_filename': output_path.name,
            'vertices_count': vertices_count,
            'faces_count': faces_count,
            'resolution': resolution,
            'generation_time_ms': round(generation_time, 2),
            'method': 'triposr_local',
            'api_credits_used': 0  # Gratuit !
        }

    except ImportError as e:
        error_msg = str(e)
        if 'tsr' in error_msg.lower():
            return {
                'success': False,
                'error': f"TripoSR non installe. Installez avec: pip install -r tools/TripoSR/requirements.txt"
            }
        return {
            'success': False,
            'error': f"Dependance manquante: {error_msg}"
        }

    except torch.cuda.OutOfMemoryError:
        return {
            'success': False,
            'error': "Memoire GPU insuffisante. Essayez une resolution plus basse ou liberez de la VRAM."
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f"Erreur TripoSR: {str(e)}",
            'error_type': type(e).__name__
        }

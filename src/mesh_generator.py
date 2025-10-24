"""
Module de génération de maillages 3D à partir d'images avec PyTorch3D
Utilise des techniques de reconstruction 3D (single-view ou multi-view)
"""

import os
import time
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import numpy as np
import trimesh
from PIL import Image

try:
    import torch
    import torchvision
    from pytorch3d.structures import Meshes
    from pytorch3d.io import save_obj
    PYTORCH3D_AVAILABLE = True
except ImportError:
    PYTORCH3D_AVAILABLE = False
    print("[!] PyTorch3D non disponible - Installation requise")


class MeshGenerator:
    """
    Générateur de maillages 3D à partir d'images

    Supporte:
    - Single-view reconstruction (une image)
    - Multi-view reconstruction (plusieurs images)
    """

    def __init__(self, device: Optional[str] = None):
        """
        Initialise le générateur

        Args:
            device: 'cuda' ou 'cpu'. Si None, détection automatique
        """
        if not PYTORCH3D_AVAILABLE:
            raise RuntimeError(
                "PyTorch3D n'est pas installé. "
                "Installez avec: conda install pytorch3d -c pytorch3d"
            )

        # Détection du device
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        print(f"[MeshGenerator] Using device: {self.device}")

        # Avertissement si CPU
        if self.device.type == "cpu":
            print("[!] [MeshGenerator] GPU non detecte - Le traitement sera plus lent")

    def load_and_preprocess_image(
        self,
        image_path: Path,
        target_size: Tuple[int, int] = (256, 256)
    ) -> torch.Tensor:
        """
        Charge et prétraite une image pour la reconstruction 3D

        Args:
            image_path: Chemin vers l'image
            target_size: Taille cible (largeur, hauteur)

        Returns:
            Tensor de l'image normalisée
        """
        # Charger l'image
        img = Image.open(image_path).convert('RGB')

        # Redimensionner
        img = img.resize(target_size, Image.Resampling.LANCZOS)

        # Convertir en tensor et normaliser [0, 1]
        img_array = np.array(img).astype(np.float32) / 255.0
        img_tensor = torch.from_numpy(img_array).permute(2, 0, 1)  # HWC -> CHW

        # Normalisation ImageNet (standard pour modèles pré-entraînés)
        normalize = torchvision.transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
        img_tensor = normalize(img_tensor)

        return img_tensor.unsqueeze(0).to(self.device)  # Ajouter batch dimension

    def generate_simple_mesh_from_depth(
        self,
        image_path: Path,
        output_path: Path,
        resolution: str = "medium"
    ) -> Dict:
        """
        Génère un maillage simple à partir d'une image en utilisant une approche basique

        Cette version est un MVP qui génère un maillage de base.
        Pour de meilleurs résultats, utilisez un modèle pré-entraîné (Pixel2Mesh, etc.)

        Args:
            image_path: Chemin vers l'image d'entrée
            output_path: Chemin de sortie pour le maillage
            resolution: 'low', 'medium', 'high'

        Returns:
            Dictionnaire avec statistiques de génération
        """
        start_time = time.time()

        # Résolution -> nombre de subdivisions
        resolution_map = {
            'low': 32,
            'medium': 64,
            'high': 128
        }
        grid_size = resolution_map.get(resolution, 64)

        print(f"[MeshGenerator] Generating mesh from {image_path.name}")
        print(f"  Resolution: {resolution} ({grid_size}x{grid_size})")

        # Charger et prétraiter l'image
        img_tensor = self.load_and_preprocess_image(image_path)

        # Pour le MVP: Générer un maillage basique à partir de l'intensité de l'image
        # Dans une version complète, on utiliserait un modèle pré-entraîné
        img_pil = Image.open(image_path).convert('L')  # Grayscale
        img_pil = img_pil.resize((grid_size, grid_size), Image.Resampling.LANCZOS)
        depth_map = np.array(img_pil).astype(np.float32) / 255.0

        # Créer la grille de vertices
        x = np.linspace(-1, 1, grid_size)
        y = np.linspace(-1, 1, grid_size)
        xx, yy = np.meshgrid(x, y)

        # Z = hauteur basée sur l'intensité
        zz = depth_map * 0.5  # Facteur d'échelle

        # Créer les vertices
        vertices = np.stack([xx.ravel(), yy.ravel(), zz.ravel()], axis=1)

        # Créer les faces (triangles)
        faces = []
        for i in range(grid_size - 1):
            for j in range(grid_size - 1):
                # Indices des 4 coins du quad
                v0 = i * grid_size + j
                v1 = i * grid_size + (j + 1)
                v2 = (i + 1) * grid_size + j
                v3 = (i + 1) * grid_size + (j + 1)

                # Deux triangles par quad
                faces.append([v0, v1, v2])
                faces.append([v1, v3, v2])

        faces = np.array(faces)

        # Créer le mesh avec Trimesh (compatible avec l'infrastructure existante)
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

        # Nettoyer le maillage
        mesh.remove_duplicate_faces()
        mesh.remove_unreferenced_vertices()

        # Sauvegarder
        mesh.export(str(output_path))

        generation_time = time.time() - start_time

        stats = {
            'success': True,
            'output_file': str(output_path),
            'vertices_count': len(mesh.vertices),
            'faces_count': len(mesh.faces),
            'resolution': resolution,
            'generation_time_ms': round(generation_time * 1000, 2),
            'device': str(self.device),
            'method': 'depth_map_basic'
        }

        print(f"  [OK] Mesh generated: {stats['vertices_count']} vertices, {stats['faces_count']} faces")
        print(f"  [TIME] {stats['generation_time_ms']:.2f}ms")

        return stats

    def generate_mesh_from_multi_view(
        self,
        image_paths: List[Path],
        output_path: Path,
        resolution: str = "medium"
    ) -> Dict:
        """
        Génère un maillage à partir de plusieurs vues (multi-view reconstruction)

        NOTE: Cette version MVP utilise la première image uniquement.
        Pour une vraie reconstruction multi-view, utilisez NeRF ou MVS.

        Args:
            image_paths: Liste de chemins vers les images
            output_path: Chemin de sortie pour le maillage
            resolution: 'low', 'medium', 'high'

        Returns:
            Dictionnaire avec statistiques de génération
        """
        if len(image_paths) == 0:
            raise ValueError("Au moins une image est requise")

        print(f"[MeshGenerator] Multi-view reconstruction from {len(image_paths)} images")

        # Pour le MVP: utiliser la premiere image
        # TODO: Implementer vraie reconstruction multi-view
        if len(image_paths) > 1:
            print("  [!] MVP: Utilisation de la premiere image uniquement")
            print("     La reconstruction multi-view complete sera implementee ulterieurement")

        # Utiliser la méthode single-view sur la première image
        return self.generate_simple_mesh_from_depth(
            image_paths[0],
            output_path,
            resolution
        )


def generate_mesh_from_images(
    image_paths: List[Path],
    output_path: Path,
    resolution: str = "medium",
    device: Optional[str] = None
) -> Dict:
    """
    Fonction principale pour générer un maillage à partir d'images

    Args:
        image_paths: Liste de chemins vers les images (1 ou plusieurs)
        output_path: Chemin de sortie pour le maillage (.obj, .stl, .ply)
        resolution: 'low', 'medium', 'high'
        device: 'cuda' ou 'cpu' (détection auto si None)

    Returns:
        Dictionnaire avec statistiques et résultat
    """
    try:
        generator = MeshGenerator(device=device)

        if len(image_paths) == 1:
            # Single-view
            return generator.generate_simple_mesh_from_depth(
                image_paths[0],
                output_path,
                resolution
            )
        else:
            # Multi-view
            return generator.generate_mesh_from_multi_view(
                image_paths,
                output_path,
                resolution
            )

    except Exception as e:
        print(f"[ERROR] [MeshGenerator] Error: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }

"""
Gestion du cache GLB pour la visualisation frontend

Les fichiers GLB sont UNIQUEMENT utilisés pour la visualisation dans le navigateur.
Toutes les opérations de traitement (simplification, réparation, etc.) utilisent
les fichiers originaux (OBJ, STL, PLY, OFF).

Architecture:
- Fichier source: data/input/bunny.obj (utilisé pour le traitement)
- Fichier GLB: data/input/bunny.glb (généré automatiquement pour la visualisation)

Le cache GLB doit être invalidé après toute modification du fichier source.
"""

from pathlib import Path
from typing import Optional


def get_glb_path(original_filename: str, base_dir: Path) -> Path:
    """
    Retourne le chemin du fichier GLB correspondant au fichier original

    Args:
        original_filename: Nom du fichier original (ex: "bunny.obj")
        base_dir: Dossier de base (généralement DATA_INPUT)

    Returns:
        Path du fichier GLB (ex: data/input/bunny.glb)
    """
    stem = Path(original_filename).stem
    return base_dir / f"{stem}.glb"


def invalidate_glb_cache(original_filename: str, base_dir: Path) -> bool:
    """
    Supprime le fichier GLB converti pour forcer la régénération

    À appeler après toute modification du fichier source :
    - Simplification
    - Réparation
    - Édition manuelle

    Args:
        original_filename: Nom du fichier original (ex: "bunny.obj")
        base_dir: Dossier de base (généralement DATA_INPUT)

    Returns:
        True si un fichier GLB a été supprimé, False sinon
    """
    glb_path = get_glb_path(original_filename, base_dir)

    if glb_path.exists():
        print(f"  🗑️ [GLB CACHE] Invalidating: {glb_path.name}")
        glb_path.unlink()
        return True

    return False


def is_glb_file(filename: str) -> bool:
    """
    Vérifie si un fichier est un GLB/GLTF

    Args:
        filename: Nom du fichier

    Returns:
        True si le fichier est GLB ou GLTF
    """
    ext = Path(filename).suffix.lower()
    return ext in {".glb", ".gltf"}


def should_convert_to_glb(filename: str, file_size: int, max_size_mb: int = 50) -> tuple[bool, Optional[str]]:
    """
    Détermine si un fichier doit être converti en GLB

    Args:
        filename: Nom du fichier
        file_size: Taille du fichier en bytes
        max_size_mb: Taille maximale pour la conversion (défaut 50MB)

    Returns:
        (should_convert, reason)
        - should_convert: True si la conversion est recommandée
        - reason: Message explicatif si should_convert est False
    """
    # Ne pas convertir si déjà GLB/GLTF
    if is_glb_file(filename):
        return False, "File is already GLB/GLTF"

    # Vérifier la taille
    size_mb = file_size / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f"File too large ({size_mb:.1f}MB > {max_size_mb}MB limit)"

    return True, None


def get_original_filename_from_glb(glb_filename: str, base_dir: Path) -> Optional[str]:
    """
    Trouve le fichier original correspondant à un GLB

    Utile pour retrouver le fichier source à partir du GLB.

    Args:
        glb_filename: Nom du fichier GLB (ex: "bunny.glb")
        base_dir: Dossier de base

    Returns:
        Nom du fichier original s'il existe, None sinon
    """
    stem = Path(glb_filename).stem

    # Chercher dans les formats supportés
    for ext in [".obj", ".stl", ".ply", ".off"]:
        original_path = base_dir / f"{stem}{ext}"
        if original_path.exists():
            return original_path.name

    return None


def cleanup_orphaned_glb_files(base_dir: Path) -> list[str]:
    """
    Supprime les fichiers GLB qui n'ont plus de fichier source correspondant

    Utile pour le nettoyage périodique du cache.

    Args:
        base_dir: Dossier de base (généralement DATA_INPUT)

    Returns:
        Liste des noms de fichiers GLB supprimés
    """
    deleted = []

    for glb_file in base_dir.glob("*.glb"):
        original = get_original_filename_from_glb(glb_file.name, base_dir)

        if original is None:
            print(f"  🗑️ [GLB CACHE] Deleting orphaned: {glb_file.name}")
            glb_file.unlink()
            deleted.append(glb_file.name)

    if deleted:
        print(f"  ✓ [GLB CACHE] Cleaned up {len(deleted)} orphaned GLB file(s)")

    return deleted


def get_cache_stats(base_dir: Path) -> dict:
    """
    Retourne des statistiques sur le cache GLB

    Args:
        base_dir: Dossier de base

    Returns:
        Dictionnaire avec les statistiques
    """
    glb_files = list(base_dir.glob("*.glb"))
    total_size = sum(f.stat().st_size for f in glb_files)

    orphaned = []
    for glb_file in glb_files:
        if get_original_filename_from_glb(glb_file.name, base_dir) is None:
            orphaned.append(glb_file.name)

    return {
        "total_glb_files": len(glb_files),
        "total_size_mb": total_size / (1024 * 1024),
        "orphaned_files": orphaned,
        "orphaned_count": len(orphaned)
    }

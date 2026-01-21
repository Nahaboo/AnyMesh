"""
Utilitaires pour la gestion des fichiers temporaires

Ce module fournit des fonctions pour gérer les fichiers temporaires
utilisés lors des conversions de format (ex: GLB → PLY pour retopologie).
"""

from pathlib import Path
import uuid
import time


def get_temp_path(prefix: str, extension: str, temp_dir: Path) -> Path:
    """
    Génère un chemin de fichier temporaire unique avec UUID.

    Args:
        prefix: Préfixe du nom de fichier (ex: "retopo_in", "segment")
        extension: Extension du fichier avec le point (ex: ".ply", ".obj")
        temp_dir: Répertoire temp où créer le fichier

    Returns:
        Path vers le fichier temporaire (non créé, juste le chemin)
    """
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir / f"{prefix}_{uuid.uuid4().hex[:8]}{extension}"


def cleanup_temp_directory(temp_dir: Path, max_age_hours: int = 1):
    """
    Supprime les fichiers temporaires plus vieux que max_age_hours.

    Cette fonction est appelée au démarrage du serveur pour nettoyer
    les fichiers orphelins laissés par des opérations échouées.

    Args:
        temp_dir: Répertoire temp à nettoyer
        max_age_hours: Âge maximum des fichiers en heures (défaut: 1h)
    """
    if not temp_dir.exists():
        return

    now = time.time()
    max_age_seconds = max_age_hours * 3600
    cleaned_count = 0

    for file in temp_dir.iterdir():
        if file.is_file():
            age = now - file.stat().st_mtime
            if age > max_age_seconds:
                try:
                    file.unlink()
                    cleaned_count += 1
                    print(f"[CLEANUP] Fichier temp supprime: {file.name}")
                except Exception as e:
                    print(f"[CLEANUP] Erreur suppression {file.name}: {e}")

    if cleaned_count > 0:
        print(f"[CLEANUP] {cleaned_count} fichier(s) temp supprime(s)")


def safe_delete(file_path: Path):
    """
    Supprime un fichier sans lever d'erreur s'il n'existe pas.

    Utile dans les blocs finally pour garantir le nettoyage
    même si le fichier n'a pas été créé.

    Args:
        file_path: Chemin du fichier à supprimer (peut être None)
    """
    if file_path and file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            print(f"[CLEANUP] Erreur suppression {file_path}: {e}")

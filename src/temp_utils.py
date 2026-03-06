"""
Temp file utilities. Handles creation and cleanup of temp files used during format conversions.
"""

from pathlib import Path
import uuid
import time


def get_temp_path(prefix: str, extension: str, temp_dir: Path) -> Path:
    """Generate a unique temp file path using UUID. The file is not created."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir / f"{prefix}_{uuid.uuid4().hex[:8]}{extension}"


def cleanup_temp_directory(temp_dir: Path, max_age_hours: int = 1):
    """Delete temp files older than max_age_hours. Called at server startup to remove orphans."""
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
                    print(f"[CLEANUP] Deleted temp file: {file.name}")
                except Exception as e:
                    print(f"[CLEANUP] Failed to delete {file.name}: {e}")

    if cleaned_count > 0:
        print(f"[CLEANUP] {cleaned_count} temp file(s) deleted")


def safe_delete(file_path: Path):
    """Delete a file silently. Safe to call in finally blocks; accepts None."""
    if file_path and file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            print(f"[CLEANUP] Failed to delete {file_path}: {e}")

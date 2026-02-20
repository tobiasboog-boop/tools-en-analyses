"""Hulpfuncties voor video metadata en formattering."""

import os
from datetime import datetime
from pathlib import Path


def format_duration(seconds: float) -> str:
    """Formatteer seconden naar MM:SS of HH:MM:SS."""
    seconds = max(0, int(seconds))
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_filesize(size_bytes: int) -> str:
    """Formatteer bytes naar leesbaar formaat (bv. '245.3 MB')."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def seconds_to_timestamp(seconds: float) -> str:
    """Converteer seconden naar HH:MM:SS.ms formaat voor FFmpeg."""
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def estimate_trimmed_size(
    original_size: int, original_duration: float, trim_duration: float
) -> int:
    """Schat de output bestandsgrootte op basis van bitrate-proportie."""
    if original_duration <= 0:
        return 0
    ratio = trim_duration / original_duration
    return int(original_size * ratio)


def get_mp4_files(folder: Path) -> list[dict]:
    """Scan map voor MP4-bestanden, gesorteerd op wijzigingsdatum (nieuwste eerst).

    Returns lijst van dicts met: path, name, size, modified
    """
    if not folder.exists():
        return []

    files = []
    for f in folder.iterdir():
        if f.suffix.lower() == ".mp4" and f.is_file():
            stat = f.stat()
            files.append(
                {
                    "path": f,
                    "name": f.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime),
                }
            )

    files.sort(key=lambda x: x["modified"], reverse=True)
    return files


def cleanup_temp_files(temp_dir: Path):
    """Verwijder alle bestanden in de temp-map."""
    if not temp_dir.exists():
        return
    for f in temp_dir.iterdir():
        if f.is_file() and f.name != ".gitkeep":
            try:
                os.remove(f)
            except OSError:
                pass

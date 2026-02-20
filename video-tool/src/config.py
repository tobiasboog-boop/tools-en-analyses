"""Configuratie voor de Notifica Video Tool."""

import os
import subprocess
from pathlib import Path

import streamlit as st

# Project root (kan op OneDrive staan)
PROJECT_ROOT = Path(__file__).parent.parent

# Bronbestanden (synchen via OneDrive, klein)
ASSETS_DIR = PROJECT_ROOT / "assets"
INTRO_DIR = PROJECT_ROOT / "intro"

# Lokale werkmap (NIET op OneDrive — grote/tijdelijke bestanden)
LOCAL_DATA_DIR = Path(os.environ.get(
    "NVT_LOCAL_DIR",
    str(Path.home() / "AppData" / "Local" / "NotificaVideoTool"),
))
LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

TEMP_DIR = LOCAL_DATA_DIR / "temp"
FFMPEG_DIR = LOCAL_DATA_DIR / "ffmpeg" / "bin"
OUTPUT_DIR = LOCAL_DATA_DIR / "output"

# Thumbnail instellingen
THUMBNAIL_INTERVAL = 10  # seconden tussen thumbnails
THUMBNAIL_WIDTH = 320    # pixels breed

# Hardware encoder cache (eenmalig getest per sessie)
_hw_encoder_cache: str | None = None


def get_ffmpeg_path() -> str:
    """Vind ffmpeg binary: eerst lokaal in ffmpeg/bin/, dan systeem PATH."""
    local = FFMPEG_DIR / "ffmpeg.exe"
    if local.exists():
        return str(local)
    return "ffmpeg"


def get_ffprobe_path() -> str:
    """Vind ffprobe binary: eerst lokaal in ffmpeg/bin/, dan systeem PATH."""
    local = FFMPEG_DIR / "ffprobe.exe"
    if local.exists():
        return str(local)
    return "ffprobe"


def get_hw_encoder() -> str:
    """Detecteer de snelste beschikbare H.264 encoder.

    Test in volgorde: h264_nvenc (NVIDIA), h264_qsv (Intel), h264_amf (AMD).
    Valt terug op libx264 als geen hardware-encoder werkt.
    Resultaat wordt gecached voor de sessie.
    """
    global _hw_encoder_cache
    if _hw_encoder_cache is not None:
        return _hw_encoder_cache

    ffmpeg = get_ffmpeg_path()
    for encoder in ["h264_nvenc", "h264_qsv", "h264_amf"]:
        try:
            result = subprocess.run(
                [ffmpeg, "-f", "lavfi", "-i", "color=black:s=64x64:d=0.1",
                 "-c:v", encoder, "-f", "null", "-"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                _hw_encoder_cache = encoder
                return encoder
        except Exception:
            continue

    _hw_encoder_cache = "libx264"
    return "libx264"


def get_secret(key: str, default: str = "") -> str:
    """Haal een secret op uit Streamlit secrets of environment variable."""
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


def get_vimeo_token() -> str:
    """Haal Vimeo access token op."""
    return get_secret("VIMEO_ACCESS_TOKEN", "")


def get_obs_folder() -> Path:
    """Haal OBS output-map op uit config of gebruik standaard Videos-map."""
    custom = get_secret("OBS_OUTPUT_FOLDER", "")
    if custom:
        return Path(custom)
    return Path.home() / "Videos"


def get_intro_path() -> Path | None:
    """Geef pad naar intro.mp4 als die bestaat."""
    path = INTRO_DIR / "intro.mp4"
    return path if path.exists() else None


def get_outro_path() -> Path | None:
    """Geef pad naar outro.mp4 als die bestaat."""
    path = INTRO_DIR / "outro.mp4"
    return path if path.exists() else None

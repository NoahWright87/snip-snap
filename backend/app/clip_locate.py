"""Locates the cached CLIP visual-encoder ONNX file. See clip_setup.py for
how it gets there (downloaded once in the background, not bundled with the
app - mirrors ffmpeg_locate.py's role for the ffmpeg binaries).
"""
from pathlib import Path
from typing import Optional

from app import config

MODEL_FILENAME = "clip_visual.onnx"


def cache_dir() -> Path:
    return config.DATA_DIR / "clip_bin"


def model_path() -> Optional[Path]:
    path = cache_dir() / MODEL_FILENAME
    return path if path.is_file() else None


def is_available() -> bool:
    return model_path() is not None

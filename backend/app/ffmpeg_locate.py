"""Locates ffmpeg/ffprobe: prefers the copy downloaded into the app's data
directory on first run (see ffmpeg_setup.py), falling back to PATH so a
developer with ffmpeg already installed doesn't need to wait on a download.
"""
import shutil
import sys
from pathlib import Path
from typing import Optional

from app import config


def cache_dir() -> Path:
    return config.DATA_DIR / "ffmpeg_bin"


def _exe_name(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def _resolve(name: str) -> Optional[str]:
    cached = cache_dir() / _exe_name(name)
    if cached.is_file():
        return str(cached)
    return shutil.which(name)


def ffmpeg_path() -> Optional[str]:
    return _resolve("ffmpeg")


def ffprobe_path() -> Optional[str]:
    return _resolve("ffprobe")


def is_available() -> bool:
    return ffmpeg_path() is not None and ffprobe_path() is not None

"""Locates ffmpeg/ffprobe: prefers a copy bundled into the packaged
executable (so end users never have to install anything), falling back to
PATH for source/dev runs.
"""
import sys
from pathlib import Path
from typing import Optional


def _bundled_dir() -> Optional[Path]:
    if not getattr(sys, "frozen", False):
        return None
    candidate = Path(sys._MEIPASS) / "ffmpeg_bin"  # type: ignore[attr-defined]
    return candidate if candidate.is_dir() else None


def _resolve(name: str) -> str:
    exe_name = f"{name}.exe" if sys.platform == "win32" else name
    bundled = _bundled_dir()
    if bundled:
        candidate = bundled / exe_name
        if candidate.is_file():
            return str(candidate)
    return name


def ffmpeg_path() -> str:
    return _resolve("ffmpeg")


def ffprobe_path() -> str:
    return _resolve("ffprobe")

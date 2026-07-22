"""Downloads and caches the CLIP visual-encoder ONNX model on first use, so
the packaged app can ship without PyTorch (see backend/ml/convert_to_onnx.py
for how the .onnx file itself gets produced).

Unlike ffmpeg_setup.py, this is *not* kicked off at app startup - library
analysis is a deliberate, user-triggered action (routes/analysis.py), so the
download only starts the first time that runs, and `ensure_clip_ready()` is
synchronous: it's meant to be called from within that action's own
background thread, not to spawn a further thread of its own.
"""
import threading
import urllib.request
from pathlib import Path
from typing import Optional

from app import clip_locate, config

_lock = threading.Lock()
_status: dict = {"state": "checking", "message": "", "progress": None}


def get_status() -> dict:
    with _lock:
        return dict(_status)


def _set_status(state: str, message: str = "", progress: Optional[float] = None) -> None:
    with _lock:
        _status["state"] = state
        _status["message"] = message
        _status["progress"] = progress


def ensure_clip_ready() -> None:
    """Blocking - downloads the model if it isn't cached yet, otherwise
    returns immediately. Call from a background thread."""
    if clip_locate.is_available():
        _set_status("ready")
        return

    _set_status("downloading", "Starting model download...", progress=0.0)
    try:
        dest_dir = clip_locate.cache_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / clip_locate.MODEL_FILENAME
        tmp_dest = dest.with_name(dest.name + ".part")
        _download(config.CLIP_MODEL_DOWNLOAD_URL, tmp_dest)
        tmp_dest.replace(dest)
        _set_status("ready")
    except Exception as exc:  # noqa: BLE001 - any failure should surface in the UI
        _set_status("error", f"model download failed: {exc}")


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=30) as resp:
        total = resp.headers.get("Content-Length")
        total_bytes = int(total) if total else None
        downloaded = 0
        chunk_size = 256 * 1024

        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                progress = (downloaded / total_bytes) if total_bytes else None
                _set_status("downloading", "Downloading model...", progress=progress)

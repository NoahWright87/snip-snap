"""Downloads and caches a working ffmpeg/ffprobe on first run (Windows only
- the only platform this app targets) so the user never has to install
anything manually. Runs in a background thread so the app is usable
immediately; export/duration-probing just wait on the result.
"""
import shutil
import sys
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

from app import config, ffmpeg_locate

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


def ensure_ffmpeg_ready() -> None:
    """Call once at startup. Non-blocking: kicks off a background download
    if needed and returns immediately so the rest of the app stays usable."""
    if ffmpeg_locate.is_available():
        _set_status("ready")
        return

    if sys.platform != "win32":
        _set_status(
            "error",
            "ffmpeg wasn't found on PATH. Install it manually and restart "
            "snip-snap (auto-download is only implemented for Windows).",
        )
        return

    _set_status("downloading", "Starting ffmpeg download...", progress=0.0)
    threading.Thread(target=_download_and_install, daemon=True).start()


def _download_and_install() -> None:
    try:
        dest_dir = ffmpeg_locate.cache_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "ffmpeg.zip"
            _download(config.FFMPEG_DOWNLOAD_URL, zip_path)
            _set_status("downloading", "Extracting ffmpeg...", progress=1.0)
            _extract_binaries(zip_path, dest_dir)

        _set_status("ready")
    except Exception as exc:  # noqa: BLE001 - any failure should surface in the UI
        _set_status("error", f"ffmpeg setup failed: {exc}")


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
                _set_status("downloading", "Downloading ffmpeg...", progress=progress)


def _extract_binaries(zip_path: Path, dest_dir: Path) -> None:
    wanted = {"ffmpeg.exe", "ffprobe.exe"}
    with zipfile.ZipFile(zip_path) as zf:
        members = [
            name
            for name in zf.namelist()
            if Path(name).name in wanted and Path(name).parent.name == "bin"
        ]
        found_names = {Path(m).name for m in members}
        if found_names != wanted:
            raise RuntimeError(f"ffmpeg archive is missing expected binaries (found {sorted(found_names)})")

        for member in members:
            target = dest_dir / Path(member).name
            tmp_target = target.with_name(target.name + ".part")
            with zf.open(member) as src, open(tmp_target, "wb") as out:
                shutil.copyfileobj(src, out)
            tmp_target.replace(target)

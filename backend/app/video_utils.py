import json
import subprocess
from pathlib import Path
from typing import Optional

from app.ffmpeg_locate import ffprobe_path
from app.proc import run_hidden


def probe_duration(path: Path) -> Optional[float]:
    """Return a video's duration in seconds via ffprobe, or None if unavailable
    (including: ffprobe hasn't finished downloading yet)."""
    ffprobe = ffprobe_path()
    if ffprobe is None:
        return None
    try:
        result = run_hidden(
            [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except (subprocess.SubprocessError, FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return None

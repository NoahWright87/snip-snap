import json
import subprocess
from pathlib import Path
from typing import Optional

from app.ffmpeg_locate import ffprobe_path


def probe_duration(path: Path) -> Optional[float]:
    """Return a video's duration in seconds via ffprobe, or None if unavailable."""
    try:
        result = subprocess.run(
            [
                ffprobe_path(),
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

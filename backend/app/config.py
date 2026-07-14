import os
from pathlib import Path

APP_NAME = "snip-snap"

DATA_DIR = Path(os.environ.get("SNIPSNAP_DATA_DIR", Path.home() / ".snip-snap"))
DB_PATH = DATA_DIR / "snip-snap.db"

HOST = "127.0.0.1"
PORT = int(os.environ.get("SNIPSNAP_PORT", "8756"))

# How long the backend will stay alive without a frontend heartbeat before
# shutting itself down. The frontend pings every 30s while a tab is open, so
# this only trips once the frontend has crashed or the window was closed
# without the pagehide beacon getting through.
HEARTBEAT_TIMEOUT_SECONDS = int(os.environ.get("SNIPSNAP_HEARTBEAT_TIMEOUT", "180"))
INACTIVITY_CHECK_INTERVAL_SECONDS = 15

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

# GPL build (not LGPL) so libx264 is included - a much better H.264 encoder
# than what's left once GPL-licensed codecs are stripped out, and quality
# actually matters for a video editor. Downloaded on first run rather than
# bundled, so the app itself stays a small download.
FFMPEG_DOWNLOAD_URL = os.environ.get(
    "SNIPSNAP_FFMPEG_URL",
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
)

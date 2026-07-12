"""Entry point for running snip-snap as a local app.

Checks whether a backend is already running on the configured port before
starting a new one, so double-launching (e.g. clicking the app icon twice)
never spawns duplicate backend processes. Opens the UI in a standalone
browser window once the server is ready.
"""
import sys
from pathlib import Path

# A --windowed/--noconsole PyInstaller build has no console, so sys.stdout/
# stderr are None. The first print() or log call would crash with nothing
# visible to explain why - redirect to a log file before anything else runs,
# so there's still somewhere to look when something goes wrong.
if getattr(sys, "frozen", False) and sys.stdout is None:
    _log_dir = Path.home() / ".snip-snap" / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _log_file = open(_log_dir / "snip-snap.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = _log_file
    sys.stderr = _log_file

import threading
import time
import urllib.error
import urllib.request

from app.browser import open_app_window
from app.config import HOST, PORT

URL = f"http://{HOST}:{PORT}"


def is_backend_running() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/health", timeout=1) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def open_when_ready() -> None:
    for _ in range(100):  # up to ~10s
        if is_backend_running():
            open_app_window(URL)
            return
        time.sleep(0.1)


def main() -> None:
    if is_backend_running():
        open_app_window(URL)
        return

    import uvicorn

    from app.main import app

    threading.Thread(target=open_when_ready, daemon=True).start()

    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    except OSError:
        # Lost the race to bind the port to another instance starting
        # at the same moment - just point the browser at it instead.
        open_app_window(URL)


if __name__ == "__main__":
    main()

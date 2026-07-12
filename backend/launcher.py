"""Entry point for running snip-snap as a local app.

Checks whether a backend is already running on the configured port before
starting a new one, so double-launching (e.g. clicking the app icon twice)
never spawns duplicate backend processes. Opens the UI in a browser window
once the server is ready.
"""
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from app.config import HOST, PORT

URL = f"http://{HOST}:{PORT}"


def is_backend_running() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/health", timeout=1) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def open_browser_when_ready() -> None:
    for _ in range(100):  # up to ~10s
        if is_backend_running():
            webbrowser.open(URL)
            return
        time.sleep(0.1)


def main() -> None:
    if is_backend_running():
        webbrowser.open(URL)
        return

    import uvicorn

    from app.main import app

    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    except OSError:
        # Lost the race to bind the port to another instance starting
        # at the same moment - just point the browser at it instead.
        webbrowser.open(URL)


if __name__ == "__main__":
    main()

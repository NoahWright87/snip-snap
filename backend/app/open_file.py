"""Opens a file with the OS's default associated app - lets the exported
file's path in the UI be a clickable "open it" link instead of just text,
since a browser page can't launch a local file itself."""
import os
import subprocess
import sys


def open_file(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=True)
    else:
        subprocess.run(["xdg-open", path], check=True)

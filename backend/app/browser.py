"""Opens the UI as a standalone, tab-less window instead of a regular
browser tab, by launching Chrome/Edge in "app mode" (--app=<url> strips the
address bar and tabs). Falls back to the OS default browser (a normal tab)
if neither can be found - relevant mainly for non-Windows dev use, since
the packaged app targets Windows, which ships Edge out of the box.
"""
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional


def _candidate_paths() -> list[str]:
    if sys.platform == "win32":
        bases = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LocalAppData"),
        ]
        names = [
            r"Microsoft\Edge\Application\msedge.exe",
            r"Google\Chrome\Application\chrome.exe",
        ]
        return [str(Path(base) / name) for base in bases if base for name in names]

    if sys.platform == "darwin":
        return [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]

    return [
        path
        for path in (
            shutil.which(name)
            for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge")
        )
        if path
    ]


def find_chromium_browser() -> Optional[str]:
    for candidate in _candidate_paths():
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def open_app_window(url: str) -> None:
    browser = find_chromium_browser()
    if browser:
        subprocess.Popen([browser, f"--app={url}"])
    else:
        webbrowser.open(url)

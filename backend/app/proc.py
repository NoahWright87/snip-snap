"""subprocess wrapper that suppresses the console window Windows otherwise
pops up when a console-subsystem child (ffmpeg.exe) is spawned from a
windowed-subsystem parent (our --windowed packaged exe has no console of
its own for the child to inherit).
"""
import subprocess
import sys


def _creationflags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def run_hidden(cmd, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, creationflags=_creationflags(), **kwargs)


def popen_hidden(cmd, **kwargs) -> subprocess.Popen:
    return subprocess.Popen(cmd, creationflags=_creationflags(), **kwargs)

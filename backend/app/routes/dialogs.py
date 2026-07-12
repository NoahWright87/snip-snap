"""Native folder/save-file pickers.

The frontend is a sandboxed browser page - it has no way to hand the
backend a real filesystem path from a picker (the File System Access API
only ever exposes opaque handles, never an OS path). But the backend is a
normal local Python process with full filesystem access, so it can just
pop a native OS dialog itself and report back the chosen path.

tkinter ships with the standard Windows Python distribution (what this app
targets) but isn't guaranteed to be present everywhere (e.g. this isn't
installed on many minimal Linux setups) - imported lazily so the app still
starts and everything else still works if it's missing; these two
endpoints just report unavailable and the frontend falls back to its
manual text field.
"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import VIDEO_EXTENSIONS

router = APIRouter(prefix="/api/dialogs", tags=["dialogs"])


class PickFolderRequest(BaseModel):
    initial_dir: Optional[str] = None


class PickSaveFileRequest(BaseModel):
    initial_dir: Optional[str] = None
    initial_file: Optional[str] = None


class PickPathResponse(BaseModel):
    path: Optional[str]


def _safe_initial_dir(path: Optional[str]) -> str:
    if path and Path(path).is_dir():
        return path
    return str(Path.home())


def _hidden_root():
    import tkinter

    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def _ask_directory(initial_dir: str) -> Optional[str]:
    from tkinter import filedialog

    root = _hidden_root()
    try:
        selected = filedialog.askdirectory(initialdir=initial_dir, parent=root)
    finally:
        root.destroy()
    return selected or None


def _ask_save_file(initial_dir: str, initial_file: str) -> Optional[str]:
    from tkinter import filedialog

    root = _hidden_root()
    try:
        pattern = " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS))
        selected = filedialog.asksaveasfilename(
            initialdir=initial_dir,
            initialfile=initial_file,
            defaultextension=".mp4",
            filetypes=[("Video files", pattern), ("All files", "*.*")],
            parent=root,
        )
    finally:
        root.destroy()
    return selected or None


@router.post("/pick-folder", response_model=PickPathResponse)
def pick_folder(payload: PickFolderRequest):
    try:
        selected = _ask_directory(_safe_initial_dir(payload.initial_dir))
    except Exception as exc:  # noqa: BLE001 - tkinter missing/unavailable, etc.
        raise HTTPException(501, f"native file picker unavailable: {exc}")
    return PickPathResponse(path=selected)


@router.post("/pick-save-file", response_model=PickPathResponse)
def pick_save_file(payload: PickSaveFileRequest):
    try:
        selected = _ask_save_file(
            _safe_initial_dir(payload.initial_dir),
            payload.initial_file or "export.mp4",
        )
    except Exception as exc:  # noqa: BLE001 - tkinter missing/unavailable, etc.
        raise HTTPException(501, f"native file picker unavailable: {exc}")
    return PickPathResponse(path=selected)

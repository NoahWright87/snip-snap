"""JSON-per-folder storage.

Each folder you point "Add folder" at gets a `.snipsnap.json` sidecar file
that is the source of truth for its videos' segments, tags, and decisions -
so the edit data travels with the video files (copy/move/back up the
folder, the edits come with it). A small central SQLite table just
remembers which folders have been added, so the library view knows where to
look without re-browsing the filesystem.

Ids are UUID strings (not autoincrement integers) since there's no longer a
single central table to hand them out from.
"""
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SIDECAR_NAME = ".snipsnap.json"

# Single process, but FastAPI runs sync routes in a threadpool - guard
# read-modify-write of the JSON files against concurrent requests.
LOCK = threading.RLock()


def new_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _sidecar_path(folder: Path) -> Path:
    return folder / SIDECAR_NAME


def _empty_folder_data() -> dict:
    return {"videos": {}}


def read_folder_data(folder: Path) -> dict:
    path = _sidecar_path(folder)
    if not path.is_file():
        return _empty_folder_data()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty_folder_data()
    data.setdefault("videos", {})
    return data


def write_folder_data(folder: Path, data: dict) -> None:
    path = _sidecar_path(folder)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    tmp_path.replace(path)


# --- Folder registry (SQLite - just remembers which folders to scan) ------


def register_folder(db, folder: Path) -> None:
    db.execute("INSERT OR IGNORE INTO folders (path) VALUES (?)", (str(folder),))
    db.commit()


def list_registered_folders(db) -> list[Path]:
    rows = db.execute("SELECT path FROM folders ORDER BY added_at").fetchall()
    return [Path(row["path"]) for row in rows]


def list_folder_rows(db) -> list[dict]:
    rows = db.execute("SELECT id, path, added_at FROM folders ORDER BY added_at").fetchall()
    return [{"id": row["id"], "path": Path(row["path"]), "added_at": row["added_at"]} for row in rows]


def remove_folder(db, folder_id: int) -> bool:
    """Un-registers a folder. Its .snipsnap.json is left on disk untouched -
    re-adding the same path later picks the data back up."""
    cur = db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
    db.commit()
    return cur.rowcount > 0


# --- Cross-folder video lookup ---------------------------------------------


def locate_video(db, video_id: str) -> Optional[tuple[Path, dict]]:
    """Finds which registered folder's sidecar contains this video id.

    Returns (folder, folder_data) - folder_data is the full parsed JSON;
    mutate folder_data["videos"][video_id] and call write_folder_data(folder,
    folder_data) to persist changes.
    """
    for folder in list_registered_folders(db):
        data = read_folder_data(folder)
        if video_id in data["videos"]:
            return folder, data
    return None

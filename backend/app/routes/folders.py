from fastapi import APIRouter, HTTPException

from app import store
from app.db import get_db
from app.schemas import FolderOut

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("", response_model=list[FolderOut])
def list_folders():
    with get_db() as db:
        rows = store.list_folder_rows(db)
    results = []
    for row in rows:
        data = store.read_folder_data(row["path"])
        results.append(
            FolderOut(id=row["id"], path=str(row["path"]), added_at=row["added_at"], video_count=len(data["videos"]))
        )
    return results


@router.delete("/{folder_id}", status_code=204)
def remove_folder(folder_id: int):
    with store.LOCK, get_db() as db:
        removed = store.remove_folder(db, folder_id)
    if not removed:
        raise HTTPException(404, "folder not registered")

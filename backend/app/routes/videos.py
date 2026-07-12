import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app import store
from app.config import VIDEO_EXTENSIONS
from app.db import get_db
from app.schemas import IngestRequest, IngestResponse, PairRequest, VideoOut
from app.video_utils import probe_duration

router = APIRouter(prefix="/api/videos", tags=["videos"])

CHUNK_SIZE = 1024 * 1024
RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def _video_out(video_id: str, folder: Path, video: dict) -> VideoOut:
    src = folder / video["filename"]
    exported_path = folder / "edited" / f"{src.stem}_edited{src.suffix}"
    segment_count = len(video["segments"])
    if exported_path.exists():
        status = "exported"
    elif segment_count > 0:
        status = "in_progress"
    else:
        status = "unprocessed"

    return VideoOut(
        id=video_id,
        filename=video["filename"],
        path=str(src),
        duration=video["duration"],
        source_type=video["source_type"],
        paired_video_id=video.get("paired_video_id"),
        created_at=video["created_at"],
        segment_count=segment_count,
        status=status,
    )


def get_video_or_404(db, video_id: str) -> tuple[Path, dict, dict]:
    """Returns (folder, folder_data, video_dict). Mutate video_dict in place
    and call store.write_folder_data(folder, folder_data) to persist."""
    located = store.locate_video(db, video_id)
    if located is None:
        raise HTTPException(404, "video not found")
    folder, data = located
    return folder, data, data["videos"][video_id]


@router.post("/ingest", response_model=IngestResponse)
def ingest_folder(payload: IngestRequest):
    folder = Path(payload.folder).expanduser()
    if not folder.is_dir():
        raise HTTPException(400, f"not a directory: {folder}")

    with store.LOCK:
        with get_db() as db:
            store.register_folder(db, folder)

        data = store.read_folder_data(folder)
        known_filenames = {v["filename"] for v in data["videos"].values()}

        added: list[str] = []
        skipped = 0
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            rel_name = path.relative_to(folder).as_posix()
            if rel_name in known_filenames:
                skipped += 1
                continue
            video_id = store.new_id()
            data["videos"][video_id] = {
                "filename": rel_name,
                "duration": probe_duration(path),
                "source_type": "unpaired",
                "paired_video_id": None,
                "created_at": store.now_iso(),
                "segments": [],
            }
            known_filenames.add(rel_name)
            added.append(video_id)

        if added:
            store.write_folder_data(folder, data)

    return IngestResponse(added=added, skipped_existing=skipped)


@router.get("", response_model=list[VideoOut])
def list_videos():
    with get_db() as db:
        folders = store.list_registered_folders(db)

    results = []
    for folder in folders:
        data = store.read_folder_data(folder)
        for video_id, video in data["videos"].items():
            results.append(_video_out(video_id, folder, video))
    results.sort(key=lambda v: v.created_at, reverse=True)
    return results


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: str):
    with get_db() as db:
        folder, _, video = get_video_or_404(db, video_id)
    return _video_out(video_id, folder, video)


@router.post("/{video_id}/pair", response_model=VideoOut)
def pair_video(video_id: str, payload: PairRequest):
    with store.LOCK, get_db() as db:
        folder, data, video = get_video_or_404(db, video_id)
        if payload.paired_video_id is not None:
            get_video_or_404(db, payload.paired_video_id)
        video["source_type"] = payload.source_type
        video["paired_video_id"] = payload.paired_video_id
        store.write_folder_data(folder, data)
    return _video_out(video_id, folder, video)


@router.get("/{video_id}/stream")
def stream_video(video_id: str, request: Request):
    with get_db() as db:
        folder, _, video = get_video_or_404(db, video_id)

    path = folder / video["filename"]
    if not path.exists():
        raise HTTPException(404, "video file missing from disk")

    file_size = path.stat().st_size
    media_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
    range_header = request.headers.get("range")

    if range_header is None:
        def full_iter():
            with open(path, "rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    yield chunk

        return StreamingResponse(
            full_iter(),
            media_type=media_type,
            headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
        )

    match = RANGE_RE.match(range_header)
    if not match:
        raise HTTPException(416, "invalid range header")

    start = int(match.group(1)) if match.group(1) else 0
    end = int(match.group(2)) if match.group(2) else file_size - 1
    end = min(end, file_size - 1)
    if start > end or start >= file_size:
        raise HTTPException(416, "range not satisfiable")

    def range_iter():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
    }
    return StreamingResponse(
        range_iter(), status_code=206, media_type=media_type, headers=headers
    )

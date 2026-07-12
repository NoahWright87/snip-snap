import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import VIDEO_EXTENSIONS
from app.db import get_db
from app.schemas import IngestRequest, IngestResponse, PairRequest, VideoOut
from app.video_utils import probe_duration

router = APIRouter(prefix="/api/videos", tags=["videos"])

CHUNK_SIZE = 1024 * 1024
RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def _row_to_video_out(db, row) -> VideoOut:
    segment_count = db.execute(
        "SELECT COUNT(*) FROM segments WHERE video_id = ?", (row["id"],)
    ).fetchone()[0]

    src = Path(row["path"])
    exported_path = src.with_name(f"{src.stem}_edited{src.suffix}")
    if exported_path.exists():
        status = "exported"
    elif segment_count > 0:
        status = "in_progress"
    else:
        status = "unprocessed"

    return VideoOut(
        id=row["id"],
        filename=row["filename"],
        path=row["path"],
        duration=row["duration"],
        source_type=row["source_type"],
        paired_video_id=row["paired_video_id"],
        created_at=row["created_at"],
        segment_count=segment_count,
        status=status,
    )


def get_video_row_or_404(db, video_id: int):
    row = db.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "video not found")
    return row


@router.post("/ingest", response_model=IngestResponse)
def ingest_folder(payload: IngestRequest):
    folder = Path(payload.folder).expanduser()
    if not folder.is_dir():
        raise HTTPException(400, f"not a directory: {folder}")

    added: list[int] = []
    skipped = 0
    with get_db() as db:
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            existing = db.execute(
                "SELECT id FROM videos WHERE path = ?", (str(path),)
            ).fetchone()
            if existing:
                skipped += 1
                continue
            duration = probe_duration(path)
            cur = db.execute(
                "INSERT INTO videos (filename, path, duration, source_type) "
                "VALUES (?, ?, ?, 'unpaired')",
                (path.name, str(path), duration),
            )
            added.append(cur.lastrowid)
        db.commit()

    return IngestResponse(added=added, skipped_existing=skipped)


@router.get("", response_model=list[VideoOut])
def list_videos():
    with get_db() as db:
        rows = db.execute("SELECT * FROM videos ORDER BY created_at DESC").fetchall()
        return [_row_to_video_out(db, row) for row in rows]


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: int):
    with get_db() as db:
        row = get_video_row_or_404(db, video_id)
        return _row_to_video_out(db, row)


@router.post("/{video_id}/pair", response_model=VideoOut)
def pair_video(video_id: int, payload: PairRequest):
    with get_db() as db:
        get_video_row_or_404(db, video_id)
        if payload.paired_video_id is not None:
            get_video_row_or_404(db, payload.paired_video_id)
        db.execute(
            "UPDATE videos SET source_type = ?, paired_video_id = ? WHERE id = ?",
            (payload.source_type, payload.paired_video_id, video_id),
        )
        db.commit()
        row = get_video_row_or_404(db, video_id)
        return _row_to_video_out(db, row)


@router.get("/{video_id}/stream")
def stream_video(video_id: int, request: Request):
    with get_db() as db:
        row = get_video_row_or_404(db, video_id)

    path = Path(row["path"])
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

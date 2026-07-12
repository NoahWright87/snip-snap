from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.routes.videos import get_video_row_or_404
from app.schemas import (
    InitSegmentsRequest,
    SegmentCreate,
    SegmentOut,
    SegmentUpdate,
    SplitSegmentRequest,
    TagRequest,
)

router = APIRouter(tags=["segments"])

# Guards against creating a sliver segment right at an existing boundary
# (e.g. clicking snip twice at nearly the same spot).
MIN_SEGMENT_LENGTH = 0.05


def _tags_for_segment(db, segment_id: int) -> list[str]:
    rows = db.execute(
        "SELECT tag FROM segment_tags WHERE segment_id = ? ORDER BY tag", (segment_id,)
    ).fetchall()
    return [row["tag"] for row in rows]


def _row_to_segment_out(db, row) -> SegmentOut:
    return SegmentOut(
        id=row["id"],
        video_id=row["video_id"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        decision=row["decision"],
        tags=_tags_for_segment(db, row["id"]),
        provenance=row["provenance"],
        created_at=row["created_at"],
    )


def _get_segment_row_or_404(db, segment_id: int):
    row = db.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "segment not found")
    return row


def _all_segments(db, video_id: int):
    return db.execute(
        "SELECT * FROM segments WHERE video_id = ? ORDER BY start_time", (video_id,)
    ).fetchall()


def _ensure_full_coverage(db, video_id: int, duration: float):
    """The timeline must always be fully partitioned into segments (the
    editor has no concept of "no segment here"). Seed one full-length
    'keep' segment the first time a video is touched."""
    existing = _all_segments(db, video_id)
    if existing:
        return existing
    db.execute(
        "INSERT INTO segments (video_id, start_time, end_time, decision, provenance) "
        "VALUES (?, 0, ?, 'keep', 'manual')",
        (video_id, duration),
    )
    db.commit()
    return _all_segments(db, video_id)


@router.get("/api/videos/{video_id}/segments", response_model=list[SegmentOut])
def list_segments(video_id: int):
    with get_db() as db:
        get_video_row_or_404(db, video_id)
        return [_row_to_segment_out(db, row) for row in _all_segments(db, video_id)]


@router.post("/api/videos/{video_id}/segments/init", response_model=list[SegmentOut])
def init_segments(video_id: int, payload: InitSegmentsRequest):
    with get_db() as db:
        get_video_row_or_404(db, video_id)
        rows = _ensure_full_coverage(db, video_id, payload.duration)
        return [_row_to_segment_out(db, row) for row in rows]


@router.post("/api/videos/{video_id}/segments/split", response_model=list[SegmentOut])
def split_segment(video_id: int, payload: SplitSegmentRequest):
    with get_db() as db:
        get_video_row_or_404(db, video_id)
        rows = _ensure_full_coverage(db, video_id, payload.duration)

        target = next(
            (r for r in rows if r["start_time"] < payload.time < r["end_time"]), None
        )
        if target is None:
            raise HTTPException(400, "split point isn't strictly inside any segment")

        if (
            payload.time - target["start_time"] < MIN_SEGMENT_LENGTH
            or target["end_time"] - payload.time < MIN_SEGMENT_LENGTH
        ):
            raise HTTPException(400, "split point is too close to an existing boundary")

        tags = _tags_for_segment(db, target["id"])
        db.execute("DELETE FROM segments WHERE id = ?", (target["id"],))
        for start, end in ((target["start_time"], payload.time), (payload.time, target["end_time"])):
            cur = db.execute(
                "INSERT INTO segments (video_id, start_time, end_time, decision, provenance) "
                "VALUES (?, ?, ?, ?, ?)",
                (video_id, start, end, target["decision"], target["provenance"]),
            )
            for tag in tags:
                db.execute(
                    "INSERT OR IGNORE INTO segment_tags (segment_id, tag) VALUES (?, ?)",
                    (cur.lastrowid, tag),
                )
        db.commit()

        return [_row_to_segment_out(db, row) for row in _all_segments(db, video_id)]


@router.post("/api/videos/{video_id}/segments", response_model=SegmentOut, status_code=201)
def create_segment(video_id: int, payload: SegmentCreate):
    if payload.end_time <= payload.start_time:
        raise HTTPException(400, "end_time must be after start_time")

    with get_db() as db:
        get_video_row_or_404(db, video_id)
        cur = db.execute(
            "INSERT INTO segments (video_id, start_time, end_time, decision, provenance) "
            "VALUES (?, ?, ?, ?, ?)",
            (video_id, payload.start_time, payload.end_time, payload.decision, payload.provenance),
        )
        for tag in payload.tags:
            db.execute(
                "INSERT OR IGNORE INTO segment_tags (segment_id, tag) VALUES (?, ?)",
                (cur.lastrowid, tag),
            )
        db.commit()
        row = db.execute("SELECT * FROM segments WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_segment_out(db, row)


@router.patch("/api/segments/{segment_id}", response_model=SegmentOut)
def update_segment(segment_id: int, payload: SegmentUpdate):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "no fields to update")

    with get_db() as db:
        _get_segment_row_or_404(db, segment_id)
        set_clause = ", ".join(f"{key} = ?" for key in updates)
        db.execute(
            f"UPDATE segments SET {set_clause} WHERE id = ?",
            (*updates.values(), segment_id),
        )
        db.commit()
        row = db.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
        return _row_to_segment_out(db, row)


@router.delete("/api/segments/{segment_id}", status_code=204)
def delete_segment(segment_id: int):
    with get_db() as db:
        _get_segment_row_or_404(db, segment_id)
        db.execute("DELETE FROM segments WHERE id = ?", (segment_id,))
        db.commit()


@router.post("/api/segments/{segment_id}/tags", response_model=SegmentOut)
def add_tag(segment_id: int, payload: TagRequest):
    tag = payload.tag.strip()
    if not tag:
        raise HTTPException(400, "tag cannot be empty")

    with get_db() as db:
        _get_segment_row_or_404(db, segment_id)
        db.execute(
            "INSERT OR IGNORE INTO segment_tags (segment_id, tag) VALUES (?, ?)",
            (segment_id, tag),
        )
        db.commit()
        row = db.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
        return _row_to_segment_out(db, row)


@router.delete("/api/segments/{segment_id}/tags/{tag}", response_model=SegmentOut)
def remove_tag(segment_id: int, tag: str):
    with get_db() as db:
        _get_segment_row_or_404(db, segment_id)
        db.execute("DELETE FROM segment_tags WHERE segment_id = ? AND tag = ?", (segment_id, tag))
        db.commit()
        row = db.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
        return _row_to_segment_out(db, row)


@router.get("/api/tags", response_model=list[str])
def list_tags():
    with get_db() as db:
        rows = db.execute("SELECT DISTINCT tag FROM segment_tags ORDER BY tag").fetchall()
        return [row["tag"] for row in rows]

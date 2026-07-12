from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.routes.videos import get_video_row_or_404
from app.schemas import SegmentCreate, SegmentOut, SegmentUpdate

router = APIRouter(tags=["segments"])


def _row_to_segment_out(row) -> SegmentOut:
    return SegmentOut(
        id=row["id"],
        video_id=row["video_id"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        decision=row["decision"],
        tag=row["tag"],
        provenance=row["provenance"],
        created_at=row["created_at"],
    )


@router.get("/api/videos/{video_id}/segments", response_model=list[SegmentOut])
def list_segments(video_id: int):
    with get_db() as db:
        get_video_row_or_404(db, video_id)
        rows = db.execute(
            "SELECT * FROM segments WHERE video_id = ? ORDER BY start_time",
            (video_id,),
        ).fetchall()
        return [_row_to_segment_out(row) for row in rows]


@router.post("/api/videos/{video_id}/segments", response_model=SegmentOut, status_code=201)
def create_segment(video_id: int, payload: SegmentCreate):
    if payload.end_time <= payload.start_time:
        raise HTTPException(400, "end_time must be after start_time")

    with get_db() as db:
        get_video_row_or_404(db, video_id)
        cur = db.execute(
            "INSERT INTO segments (video_id, start_time, end_time, decision, tag, provenance) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                video_id,
                payload.start_time,
                payload.end_time,
                payload.decision,
                payload.tag,
                payload.provenance,
            ),
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM segments WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _row_to_segment_out(row)


def _get_segment_row_or_404(db, segment_id: int):
    row = db.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "segment not found")
    return row


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
        return _row_to_segment_out(row)


@router.delete("/api/segments/{segment_id}", status_code=204)
def delete_segment(segment_id: int):
    with get_db() as db:
        _get_segment_row_or_404(db, segment_id)
        db.execute("DELETE FROM segments WHERE id = ?", (segment_id,))
        db.commit()


@router.get("/api/tags", response_model=list[str])
def list_tags():
    with get_db() as db:
        rows = db.execute(
            "SELECT DISTINCT tag FROM segments WHERE tag IS NOT NULL ORDER BY tag"
        ).fetchall()
        return [row["tag"] for row in rows]

from fastapi import APIRouter, HTTPException

from app import store
from app.db import get_db
from app.routes.videos import get_video_or_404
from app.schemas import (
    InitSegmentsRequest,
    MergeSegmentsRequest,
    ReplaceSegmentsRequest,
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


def _segment_out(video_id: str, seg: dict) -> SegmentOut:
    return SegmentOut(
        id=seg["id"],
        video_id=video_id,
        start_time=seg["start_time"],
        end_time=seg["end_time"],
        decision=seg["decision"],
        tags=seg["tags"],
        provenance=seg["provenance"],
        created_at=seg["created_at"],
    )


def _sorted_out(video_id: str, video: dict) -> list[SegmentOut]:
    ordered = sorted(video["segments"], key=lambda s: s["start_time"])
    return [_segment_out(video_id, s) for s in ordered]


def _find_segment(video: dict, segment_id: str) -> dict:
    for seg in video["segments"]:
        if seg["id"] == segment_id:
            return seg
    raise HTTPException(404, "segment not found")


def _find_segment_anywhere(db, segment_id: str):
    """Segment routes are keyed by segment_id alone (no video_id in the
    path), so search every registered folder's videos for it."""
    for folder in store.list_registered_folders(db):
        data = store.read_folder_data(folder)
        for video_id, video in data["videos"].items():
            for seg in video["segments"]:
                if seg["id"] == segment_id:
                    return folder, data, video_id, video, seg
    raise HTTPException(404, "segment not found")


def _ensure_full_coverage(video: dict, duration: float) -> None:
    """The timeline must always be fully partitioned into segments (the
    editor has no concept of "no segment here"). Seed one full-length
    'keep' segment the first time a video is touched."""
    if video["segments"]:
        return
    video["segments"] = [
        {
            "id": store.new_id(),
            "start_time": 0.0,
            "end_time": duration,
            "decision": "keep",
            "tags": [],
            "provenance": "manual",
            "created_at": store.now_iso(),
        }
    ]


@router.get("/api/videos/{video_id}/segments", response_model=list[SegmentOut])
def list_segments(video_id: str):
    with get_db() as db:
        _, _, video = get_video_or_404(db, video_id)
    return _sorted_out(video_id, video)


@router.post("/api/videos/{video_id}/segments/init", response_model=list[SegmentOut])
def init_segments(video_id: str, payload: InitSegmentsRequest):
    with store.LOCK, get_db() as db:
        folder, data, video = get_video_or_404(db, video_id)
        _ensure_full_coverage(video, payload.duration)
        store.write_folder_data(folder, data)
        return _sorted_out(video_id, video)


@router.post("/api/videos/{video_id}/segments/split", response_model=list[SegmentOut])
def split_segment(video_id: str, payload: SplitSegmentRequest):
    with store.LOCK, get_db() as db:
        folder, data, video = get_video_or_404(db, video_id)
        _ensure_full_coverage(video, payload.duration)

        target = next(
            (s for s in video["segments"] if s["start_time"] < payload.time < s["end_time"]),
            None,
        )
        if target is None:
            raise HTTPException(400, "split point isn't strictly inside any segment")
        if (
            payload.time - target["start_time"] < MIN_SEGMENT_LENGTH
            or target["end_time"] - payload.time < MIN_SEGMENT_LENGTH
        ):
            raise HTTPException(400, "split point is too close to an existing boundary")

        video["segments"].remove(target)
        for start, end in ((target["start_time"], payload.time), (payload.time, target["end_time"])):
            video["segments"].append(
                {
                    "id": store.new_id(),
                    "start_time": start,
                    "end_time": end,
                    "decision": target["decision"],
                    "tags": list(target["tags"]),
                    "provenance": target["provenance"],
                    "created_at": store.now_iso(),
                }
            )

        store.write_folder_data(folder, data)
        return _sorted_out(video_id, video)


@router.post("/api/videos/{video_id}/segments/merge", response_model=list[SegmentOut])
def merge_segments(video_id: str, payload: MergeSegmentsRequest):
    """Removes a snip: merges the two segments meeting at `time` back into
    one. Tags and decision are cleared on the merged result - a tag applied
    to one side (or the other) doesn't obviously apply to the whole thing
    once they're rejoined."""
    with store.LOCK, get_db() as db:
        folder, data, video = get_video_or_404(db, video_id)

        left = next((s for s in video["segments"] if s["end_time"] == payload.time), None)
        right = next((s for s in video["segments"] if s["start_time"] == payload.time), None)
        if left is None or right is None:
            raise HTTPException(400, "no split boundary at that time")

        video["segments"].remove(left)
        video["segments"].remove(right)
        video["segments"].append(
            {
                "id": store.new_id(),
                "start_time": left["start_time"],
                "end_time": right["end_time"],
                "decision": "keep",
                "tags": [],
                "provenance": "manual",
                "created_at": store.now_iso(),
            }
        )

        store.write_folder_data(folder, data)
        return _sorted_out(video_id, video)


@router.put("/api/videos/{video_id}/segments", response_model=list[SegmentOut])
def replace_segments(video_id: str, payload: ReplaceSegmentsRequest):
    """Wholesale replace - used by the frontend's undo/redo, which snapshots
    and restores the full segment list rather than trying to model an
    inverse for every possible edit."""
    if not payload.segments:
        raise HTTPException(400, "segments cannot be empty")

    with store.LOCK, get_db() as db:
        folder, data, video = get_video_or_404(db, video_id)
        video["segments"] = [
            {
                "id": store.new_id(),
                "start_time": s.start_time,
                "end_time": s.end_time,
                "decision": s.decision,
                "tags": list(s.tags),
                "provenance": "manual",
                "created_at": store.now_iso(),
            }
            for s in payload.segments
        ]
        store.write_folder_data(folder, data)
        return _sorted_out(video_id, video)


@router.post("/api/videos/{video_id}/segments", response_model=SegmentOut, status_code=201)
def create_segment(video_id: str, payload: SegmentCreate):
    if payload.end_time <= payload.start_time:
        raise HTTPException(400, "end_time must be after start_time")

    with store.LOCK, get_db() as db:
        folder, data, video = get_video_or_404(db, video_id)
        seg = {
            "id": store.new_id(),
            "start_time": payload.start_time,
            "end_time": payload.end_time,
            "decision": payload.decision,
            "tags": list(payload.tags),
            "provenance": payload.provenance,
            "created_at": store.now_iso(),
        }
        video["segments"].append(seg)
        store.write_folder_data(folder, data)
        return _segment_out(video_id, seg)


@router.patch("/api/segments/{segment_id}", response_model=SegmentOut)
def update_segment(segment_id: str, payload: SegmentUpdate):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "no fields to update")

    with store.LOCK, get_db() as db:
        folder, data, video_id, video, seg = _find_segment_anywhere(db, segment_id)
        seg.update(updates)
        store.write_folder_data(folder, data)
        return _segment_out(video_id, seg)


@router.delete("/api/segments/{segment_id}", status_code=204)
def delete_segment(segment_id: str):
    with store.LOCK, get_db() as db:
        folder, data, video_id, video, seg = _find_segment_anywhere(db, segment_id)
        video["segments"].remove(seg)
        store.write_folder_data(folder, data)


@router.post("/api/segments/{segment_id}/tags", response_model=SegmentOut)
def add_tag(segment_id: str, payload: TagRequest):
    tag = payload.tag.strip()
    if not tag:
        raise HTTPException(400, "tag cannot be empty")

    with store.LOCK, get_db() as db:
        folder, data, video_id, video, seg = _find_segment_anywhere(db, segment_id)
        if tag not in seg["tags"]:
            seg["tags"] = sorted(seg["tags"] + [tag])
        store.write_folder_data(folder, data)
        return _segment_out(video_id, seg)


@router.delete("/api/segments/{segment_id}/tags/{tag}", response_model=SegmentOut)
def remove_tag(segment_id: str, tag: str):
    with store.LOCK, get_db() as db:
        folder, data, video_id, video, seg = _find_segment_anywhere(db, segment_id)
        seg["tags"] = [t for t in seg["tags"] if t != tag]
        store.write_folder_data(folder, data)
        return _segment_out(video_id, seg)


@router.get("/api/tags", response_model=list[str])
def list_tags():
    with get_db() as db:
        tags: set[str] = set()
        for folder in store.list_registered_folders(db):
            data = store.read_folder_data(folder)
            for video in data["videos"].values():
                for seg in video["segments"]:
                    tags.update(seg["tags"])
    return sorted(tags)

"""Runs CLIP embedding analysis across the whole library as a background
job, triggered by the editor's "Analyze library" button. Deliberately not
automatic (unlike ffmpeg setup) - the user chose an explicit trigger since
this is real, potentially lengthy CPU work, and they want to control when it
happens rather than have it start silently.

One job at a time, library-wide rather than per-video (unlike export.py):
embeddings need to accumulate across the whole library, not one video, for
a tag's classifier to eventually have enough examples (see ml/sanity_check.py).
"""
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app import clip_setup, store
from app.db import get_db
from app.schemas import AnalysisStatus

from ml import embeddings

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

_lock = threading.Lock()
_status: dict = {"state": "idle", "progress": None, "message": ""}


def _set_status(**fields) -> None:
    with _lock:
        _status.update(fields)


def _get_status() -> dict:
    with _lock:
        return dict(_status)


def _collect_pending_work() -> list[tuple[Path, str, list[dict], dict]]:
    """One entry per video with un-cached segments: (video_path, video_id,
    pending_segments, existing_cache). Videos with nothing new, or whose
    source file is missing, are skipped."""
    with get_db() as db:
        folders = store.list_registered_folders(db)

    work = []
    for folder in folders:
        data = store.read_folder_data(folder)
        for video_id, video in data.get("videos", {}).items():
            video_path = folder / video["filename"]
            if not video_path.is_file():
                continue
            cache = embeddings.load_cache(video_id)
            pending = [s for s in video.get("segments", []) if s["id"] not in cache]
            if pending:
                work.append((video_path, video_id, pending, cache))
    return work


def _run_analysis() -> None:
    try:
        _set_status(state="downloading_model", progress=None, message="Setting up the analysis model...")
        clip_setup.ensure_clip_ready()
        clip_status = clip_setup.get_status()
        if clip_status["state"] != "ready":
            _set_status(state="failed", message=clip_status["message"] or "model setup failed")
            return

        work = _collect_pending_work()
        total = sum(len(pending) for _, _, pending, _ in work)
        if total == 0:
            _set_status(state="succeeded", progress=1.0, message="Nothing new to analyze.")
            return

        done = 0
        _set_status(state="running", progress=0.0, message=f"0/{total} clips analyzed")
        for video_path, video_id, pending, cache in work:
            for segment in pending:
                vector = embeddings.embed_segment(video_path, segment["start_time"], segment["end_time"])
                if vector is not None:
                    cache[segment["id"]] = vector
                done += 1
                _set_status(progress=done / total, message=f"{done}/{total} clips analyzed")
            embeddings.save_cache(video_id, cache)

        _set_status(state="succeeded", progress=1.0, message=f"Analyzed {total} clip(s).")
    except Exception as exc:  # noqa: BLE001 - any failure should surface in the UI
        _set_status(state="failed", message=str(exc))


@router.post("/run", response_model=AnalysisStatus, status_code=202)
def run_analysis():
    if _get_status()["state"] in ("downloading_model", "running"):
        raise HTTPException(409, "analysis is already running")

    _set_status(state="downloading_model", progress=None, message="Starting...")
    threading.Thread(target=_run_analysis, daemon=True).start()
    return _get_status()


@router.get("/status", response_model=AnalysisStatus)
def analysis_status():
    return _get_status()

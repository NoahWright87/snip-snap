import subprocess
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

from app import ffmpeg_setup
from app.db import get_db
from app.ffmpeg_locate import ffmpeg_path
from app.proc import popen_hidden
from app.routes.videos import get_video_row_or_404
from app.schemas import ExportJobStatus, ExportRequest

router = APIRouter(prefix="/api/videos", tags=["export"])

# 1080p/720p cap height without ever upscaling smaller sources; -2 keeps
# width even (required by libx264) while preserving aspect ratio.
RESOLUTION_FILTERS: dict[str, Optional[str]] = {
    "1080p": "scale=-2:'min(1080,ih)'",
    "720p": "scale=-2:'min(720,ih)'",
    "original": None,
}

_jobs_lock = threading.Lock()
_jobs: dict[int, dict] = {}


def _update_job(video_id: int, **fields) -> None:
    with _jobs_lock:
        _jobs.setdefault(video_id, {}).update(fields)


def _get_job(video_id: int) -> dict:
    with _jobs_lock:
        job = _jobs.get(video_id, {})
    return {
        "state": job.get("state", "idle"),
        "progress": job.get("progress"),
        "output_path": job.get("output_path"),
        "error": job.get("error"),
    }


def _build_filter_complex(segments: list, resolution: str) -> tuple[str, list[str]]:
    filter_parts = []
    stream_labels = []
    for i, seg in enumerate(segments):
        filter_parts.append(
            f"[0:v]trim=start={seg['start_time']}:end={seg['end_time']},"
            f"setpts=PTS-STARTPTS[v{i}];"
            f"[0:a]atrim=start={seg['start_time']}:end={seg['end_time']},"
            f"asetpts=PTS-STARTPTS[a{i}];"
        )
        stream_labels.append(f"[v{i}][a{i}]")

    video_label = "outv"
    filter_complex = (
        "".join(filter_parts)
        + "".join(stream_labels)
        + f"concat=n={len(segments)}:v=1:a=1[{video_label}][outa]"
    )

    scale_filter = RESOLUTION_FILTERS.get(resolution)
    if scale_filter:
        filter_complex += f";[{video_label}]{scale_filter}[scaledv]"
        video_label = "scaledv"

    return filter_complex, [f"[{video_label}]", "[outa]"]


def _run_export(video_id: int, cmd: list[str], out_path: Path, total_duration: float) -> None:
    try:
        proc = popen_hidden(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

        stderr_lines: list[str] = []

        def _drain_stderr():
            for line in proc.stderr:
                stderr_lines.append(line)

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_ms=") and total_duration > 0:
                try:
                    # ffmpeg's -progress output confusingly reports this
                    # field in microseconds, not milliseconds.
                    out_time_s = int(line.split("=", 1)[1]) / 1_000_000
                    _update_job(video_id, progress=min(0.99, out_time_s / total_duration))
                except ValueError:
                    pass

        proc.wait()
        stderr_thread.join(timeout=5)

        if proc.returncode == 0:
            _update_job(video_id, state="succeeded", progress=1.0, output_path=str(out_path), error=None)
        else:
            _update_job(video_id, state="failed", error="".join(stderr_lines)[-2000:] or "ffmpeg exited with an error")
    except Exception as exc:  # noqa: BLE001 - report any failure to the UI
        _update_job(video_id, state="failed", error=str(exc))


@router.post("/{video_id}/export", response_model=ExportJobStatus, status_code=202)
def export_video(video_id: int, payload: ExportRequest):
    with get_db() as db:
        row = get_video_row_or_404(db, video_id)
        segments = db.execute(
            "SELECT start_time, end_time FROM segments "
            "WHERE video_id = ? AND decision = 'keep' ORDER BY start_time",
            (video_id,),
        ).fetchall()

    if not segments:
        raise HTTPException(400, "no kept segments to export")

    if _get_job(video_id)["state"] == "running":
        raise HTTPException(409, "an export is already in progress for this video")

    src = Path(row["path"])
    if not src.exists():
        raise HTTPException(404, "source video file missing from disk")

    ffmpeg_bin = ffmpeg_path()
    if ffmpeg_bin is None:
        status = ffmpeg_setup.get_status()
        raise HTTPException(
            409,
            f"ffmpeg isn't ready yet ({status['state']}: {status['message'] or 'still setting up'}). "
            "Try again in a moment.",
        )

    if payload.output_path:
        out_path = Path(payload.output_path)
    else:
        out_path = src.parent / "edited" / f"{src.stem}_edited{src.suffix}"

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(400, f"couldn't create output folder {out_path.parent}: {exc}")

    filter_complex, output_maps = _build_filter_complex(segments, payload.resolution)
    total_duration = sum(seg["end_time"] - seg["start_time"] for seg in segments)

    cmd = [ffmpeg_bin, "-y", "-i", str(src), "-filter_complex", filter_complex]
    for m in output_maps:
        cmd += ["-map", m]
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-progress", "pipe:1", "-nostats",
        str(out_path),
    ]

    _update_job(video_id, state="running", progress=0.0, output_path=None, error=None)
    threading.Thread(target=_run_export, args=(video_id, cmd, out_path, total_duration), daemon=True).start()

    return _get_job(video_id)


@router.get("/{video_id}/export/status", response_model=ExportJobStatus)
def export_status(video_id: int):
    return _get_job(video_id)

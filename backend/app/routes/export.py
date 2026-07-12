import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.ffmpeg_locate import ffmpeg_path
from app.routes.videos import get_video_row_or_404
from app.schemas import ExportResponse

router = APIRouter(prefix="/api/videos", tags=["export"])


def _build_filter_complex(segments: list) -> tuple[str, list[str]]:
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
    concat = (
        "".join(stream_labels)
        + f"concat=n={len(segments)}:v=1:a=1[outv][outa]"
    )
    return "".join(filter_parts) + concat, ["[outv]", "[outa]"]


@router.post("/{video_id}/export", response_model=ExportResponse)
def export_video(video_id: int):
    with get_db() as db:
        row = get_video_row_or_404(db, video_id)
        segments = db.execute(
            "SELECT start_time, end_time FROM segments "
            "WHERE video_id = ? AND decision = 'keep' ORDER BY start_time",
            (video_id,),
        ).fetchall()

    if not segments:
        raise HTTPException(400, "no kept segments to export")

    src = Path(row["path"])
    if not src.exists():
        raise HTTPException(404, "source video file missing from disk")

    out_path = src.with_name(f"{src.stem}_edited{src.suffix}")
    filter_complex, output_maps = _build_filter_complex(segments)

    cmd = [ffmpeg_path(), "-y", "-i", str(src), "-filter_complex", filter_complex]
    for m in output_maps:
        cmd += ["-map", m]
    cmd.append(str(out_path))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    except FileNotFoundError:
        raise HTTPException(500, "ffmpeg is not installed or not on PATH")

    if result.returncode != 0:
        raise HTTPException(500, f"ffmpeg export failed: {result.stderr[-2000:]}")

    return ExportResponse(output_path=str(out_path))

import os
import stat
import time
from pathlib import Path


def _make_video(client, tmp_path, name="clip.mp4"):
    folder = tmp_path / "library"
    folder.mkdir(exist_ok=True)
    (folder / name).write_bytes(b"x")
    client.post("/api/videos/ingest", json={"folder": str(folder)})
    videos = {v["filename"]: v for v in client.get("/api/videos").json()}
    return videos[name]["id"]


def _write_fake_ffmpeg(tmp_path: Path, *, exit_code: int = 0, delay: float = 0.0) -> str:
    """A stand-in for ffmpeg that speaks just enough of the -progress
    protocol to exercise our progress parsing, without needing a real
    ffmpeg binary in the test environment."""
    script = tmp_path / "fake-ffmpeg.sh"
    script.write_text(
        f"""#!/bin/sh
for arg; do :; done  # $arg ends up holding the last positional (output path)
echo "out_time_ms=500000"
sleep {delay}
echo "out_time_ms=1000000"
echo "progress=end"
if [ {exit_code} -eq 0 ]; then
  touch "$arg"
else
  echo "fake ffmpeg exploded" >&2
fi
exit {exit_code}
"""
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script)


def _poll_until_done(client, video_id, timeout=5):
    deadline = time.time() + timeout
    status = None
    while time.time() < deadline:
        status = client.get(f"/api/videos/{video_id}/export/status").json()
        if status["state"] not in ("idle", "running"):
            return status
        time.sleep(0.05)
    return status


def test_export_rejects_no_kept_segments(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    resp = client.post(f"/api/videos/{video_id}/export", json={})
    assert resp.status_code == 400


def test_export_status_is_idle_before_anything_runs(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    status = client.get(f"/api/videos/{video_id}/export/status").json()
    assert status == {"state": "idle", "progress": None, "output_path": None, "error": None}


def test_export_reports_ffmpeg_not_ready(client, tmp_path, monkeypatch):
    video_id = _make_video(client, tmp_path)
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 1, "decision": "keep"},
    )
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: None)

    resp = client.post(f"/api/videos/{video_id}/export", json={})
    assert resp.status_code == 409
    assert "ffmpeg isn't ready" in resp.json()["detail"]


def test_export_runs_in_background_and_reports_progress(client, tmp_path, monkeypatch):
    video_id = _make_video(client, tmp_path)
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 2, "decision": "keep"},
    )
    fake_ffmpeg = _write_fake_ffmpeg(tmp_path)
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: fake_ffmpeg)

    resp = client.post(f"/api/videos/{video_id}/export", json={})
    assert resp.status_code == 202
    assert resp.json()["state"] == "running"

    status = _poll_until_done(client, video_id)
    assert status["state"] == "succeeded"
    assert status["progress"] == 1.0
    assert os.path.exists(status["output_path"])


def test_export_reports_failure(client, tmp_path, monkeypatch):
    video_id = _make_video(client, tmp_path)
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 1, "decision": "keep"},
    )
    fake_ffmpeg = _write_fake_ffmpeg(tmp_path, exit_code=1)
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: fake_ffmpeg)

    client.post(f"/api/videos/{video_id}/export", json={})
    status = _poll_until_done(client, video_id)

    assert status["state"] == "failed"
    assert status["error"]


def test_export_rejects_concurrent_runs(client, tmp_path, monkeypatch):
    video_id = _make_video(client, tmp_path)
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 1, "decision": "keep"},
    )
    fake_ffmpeg = _write_fake_ffmpeg(tmp_path, delay=0.5)
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: fake_ffmpeg)

    first = client.post(f"/api/videos/{video_id}/export", json={})
    assert first.status_code == 202

    second = client.post(f"/api/videos/{video_id}/export", json={})
    assert second.status_code == 409

    _poll_until_done(client, video_id)


def test_export_custom_resolution_and_output_path(client, tmp_path, monkeypatch):
    video_id = _make_video(client, tmp_path)
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 1, "decision": "keep"},
    )
    fake_ffmpeg = _write_fake_ffmpeg(tmp_path)
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: fake_ffmpeg)

    out_dir = tmp_path / "exports"
    out_dir.mkdir()
    custom_path = str(out_dir / "my-cut.mp4")

    resp = client.post(
        f"/api/videos/{video_id}/export",
        json={"output_path": custom_path, "resolution": "720p"},
    )
    assert resp.status_code == 202

    status = _poll_until_done(client, video_id)
    assert status["state"] == "succeeded"
    assert status["output_path"] == custom_path


def test_export_rejects_output_path_with_missing_folder(client, tmp_path, monkeypatch):
    video_id = _make_video(client, tmp_path)
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 1, "decision": "keep"},
    )
    fake_ffmpeg = _write_fake_ffmpeg(tmp_path)
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: fake_ffmpeg)

    resp = client.post(
        f"/api/videos/{video_id}/export",
        json={"output_path": str(tmp_path / "nope" / "out.mp4")},
    )
    assert resp.status_code == 400

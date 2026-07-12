import time


def _make_video(client, tmp_path, name="clip.mp4"):
    folder = tmp_path / "library"
    folder.mkdir(exist_ok=True)
    (folder / name).write_bytes(b"x")
    client.post("/api/videos/ingest", json={"folder": str(folder)})
    videos = {v["filename"]: v for v in client.get("/api/videos").json()}
    return videos[name]["id"]


class _FakePopen:
    """Stands in for subprocess.Popen so export tests don't need a real,
    platform-specific ffmpeg binary to exercise the progress-parsing and
    job-state-machine logic (a real shell/batch script stand-in isn't
    portable: Windows can't directly exec a #!/bin/sh script)."""

    def __init__(self, stdout_lines=(), returncode=0, stderr_lines=()):
        self.stdout = iter(stdout_lines)
        self.stderr = iter(stderr_lines)
        self.returncode = returncode

    def wait(self):
        return self.returncode


def _progress_lines(delay=0.0):
    yield "out_time_ms=500000\n"
    if delay:
        time.sleep(delay)
    yield "out_time_ms=1000000\n"
    yield "progress=end\n"


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


def _poll_until_done(client, video_id, timeout=5):
    deadline = time.time() + timeout
    status = None
    while time.time() < deadline:
        status = client.get(f"/api/videos/{video_id}/export/status").json()
        if status["state"] not in ("idle", "running"):
            return status
        time.sleep(0.05)
    return status


def test_export_runs_in_background_and_reports_progress(client, tmp_path, monkeypatch):
    video_id = _make_video(client, tmp_path)
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 2, "decision": "keep"},
    )
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: "fake-ffmpeg")
    monkeypatch.setattr(
        "app.routes.export.popen_hidden",
        lambda cmd, **kw: _FakePopen(stdout_lines=_progress_lines()),
    )

    resp = client.post(f"/api/videos/{video_id}/export", json={})
    assert resp.status_code == 202
    assert resp.json()["state"] == "running"

    status = _poll_until_done(client, video_id)
    assert status["state"] == "succeeded"
    assert status["progress"] == 1.0
    assert status["output_path"]


def test_export_reports_failure(client, tmp_path, monkeypatch):
    video_id = _make_video(client, tmp_path)
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 1, "decision": "keep"},
    )
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: "fake-ffmpeg")
    monkeypatch.setattr(
        "app.routes.export.popen_hidden",
        lambda cmd, **kw: _FakePopen(
            stdout_lines=_progress_lines(), returncode=1, stderr_lines=["fake ffmpeg exploded\n"]
        ),
    )

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
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: "fake-ffmpeg")
    monkeypatch.setattr(
        "app.routes.export.popen_hidden",
        lambda cmd, **kw: _FakePopen(stdout_lines=_progress_lines(delay=0.5)),
    )

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
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: "fake-ffmpeg")
    monkeypatch.setattr(
        "app.routes.export.popen_hidden",
        lambda cmd, **kw: _FakePopen(stdout_lines=_progress_lines()),
    )

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
    monkeypatch.setattr("app.routes.export.ffmpeg_path", lambda: "fake-ffmpeg")

    resp = client.post(
        f"/api/videos/{video_id}/export",
        json={"output_path": str(tmp_path / "nope" / "out.mp4")},
    )
    assert resp.status_code == 400


def test_build_filter_complex_applies_resolution_cap(client, tmp_path):
    from app.routes.export import _build_filter_complex

    segments = [{"start_time": 0, "end_time": 1}]

    filter_complex, output_maps = _build_filter_complex(segments, "1080p")
    assert "scale=-2:'min(1080,ih)'" in filter_complex
    assert output_maps == ["[scaledv]", "[outa]"]

    filter_complex, output_maps = _build_filter_complex(segments, "original")
    assert "scale=" not in filter_complex
    assert output_maps == ["[outv]", "[outa]"]

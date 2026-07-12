import shutil

import pytest


def _make_video(client, tmp_path, name="clip.mp4"):
    folder = tmp_path / "library"
    folder.mkdir(exist_ok=True)
    (folder / name).write_bytes(b"x")
    client.post("/api/videos/ingest", json={"folder": str(folder)})
    videos = {v["filename"]: v for v in client.get("/api/videos").json()}
    return videos[name]["id"]


def test_export_rejects_no_kept_segments(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    resp = client.post(f"/api/videos/{video_id}/export")
    assert resp.status_code == 400


@pytest.mark.skipif(shutil.which("ffmpeg") is not None, reason="only exercises the missing-ffmpeg path")
def test_export_reports_missing_ffmpeg_cleanly(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 1, "decision": "keep"},
    )
    resp = client.post(f"/api/videos/{video_id}/export")
    assert resp.status_code == 500
    assert "ffmpeg" in resp.json()["detail"].lower()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="requires a real ffmpeg binary")
def test_export_trims_and_concatenates_real_video(client, tmp_path):
    import subprocess

    folder = tmp_path / "library"
    folder.mkdir()
    src = folder / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=4",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-shortest", "-c:v", "libx264", "-c:a", "aac", str(src),
        ],
        capture_output=True,
        check=True,
    )

    client.post("/api/videos/ingest", json={"folder": str(folder)})
    video_id = client.get("/api/videos").json()[0]["id"]

    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 1, "decision": "keep"},
    )
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 1, "end_time": 2, "decision": "cut"},
    )
    client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 2, "end_time": 3, "decision": "keep"},
    )

    resp = client.post(f"/api/videos/{video_id}/export")
    assert resp.status_code == 200
    out_path = resp.json()["output_path"]
    assert out_path.endswith("clip_edited.mp4")

    from pathlib import Path

    assert Path(out_path).exists()

    video = client.get(f"/api/videos/{video_id}").json()
    assert video["status"] == "exported"

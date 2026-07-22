import time

import numpy as np

from app import clip_setup
from ml import embeddings


def _make_video_with_segment(client, tmp_path, name="clip.mp4"):
    folder = tmp_path / "library"
    folder.mkdir(exist_ok=True)
    (folder / name).write_bytes(b"x")
    client.post("/api/videos/ingest", json={"folder": str(folder)})
    video_id = client.get("/api/videos").json()[0]["id"]
    client.post(f"/api/videos/{video_id}/segments/init", json={"duration": 10})
    return video_id


def _poll_until_done(client, timeout=5):
    deadline = time.time() + timeout
    status = None
    while time.time() < deadline:
        status = client.get("/api/analysis/status").json()
        if status["state"] not in ("idle", "downloading_model", "running"):
            return status
        time.sleep(0.05)
    return status


def _stub_clip_ready(monkeypatch):
    monkeypatch.setattr(clip_setup, "ensure_clip_ready", lambda: None)
    monkeypatch.setattr(clip_setup, "get_status", lambda: {"state": "ready", "message": "", "progress": None})


def test_status_is_idle_before_anything_runs(client):
    assert client.get("/api/analysis/status").json() == {"state": "idle", "message": "", "progress": None}


def test_run_with_nothing_to_analyze_succeeds_immediately(client, monkeypatch):
    _stub_clip_ready(monkeypatch)

    resp = client.post("/api/analysis/run")
    assert resp.status_code == 202

    status = _poll_until_done(client)
    assert status["state"] == "succeeded"
    assert "Nothing" in status["message"]


def test_run_embeds_and_caches_every_segment(client, tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings, "CACHE_DIR", tmp_path / "embeddings_cache")
    _stub_clip_ready(monkeypatch)
    fake_vector = np.array([1.0, 2.0, 3.0])
    monkeypatch.setattr(embeddings, "embed_segment", lambda *a, **kw: fake_vector)

    video_id = _make_video_with_segment(client, tmp_path)

    resp = client.post("/api/analysis/run")
    assert resp.status_code == 202

    status = _poll_until_done(client)
    assert status["state"] == "succeeded"
    assert status["progress"] == 1.0

    segment_id = client.get(f"/api/videos/{video_id}/segments").json()[0]["id"]
    cache = embeddings.load_cache(video_id)
    assert set(cache) == {segment_id}
    np.testing.assert_array_equal(cache[segment_id], fake_vector)


def test_run_reports_failure_if_model_setup_fails(client, tmp_path, monkeypatch):
    monkeypatch.setattr(clip_setup, "ensure_clip_ready", lambda: None)
    monkeypatch.setattr(
        clip_setup, "get_status", lambda: {"state": "error", "message": "model download failed: boom", "progress": None}
    )
    _make_video_with_segment(client, tmp_path)

    resp = client.post("/api/analysis/run")
    assert resp.status_code == 202

    status = _poll_until_done(client)
    assert status["state"] == "failed"
    assert "boom" in status["message"]


def test_run_rejects_concurrent_runs(client, tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings, "CACHE_DIR", tmp_path / "embeddings_cache")
    _stub_clip_ready(monkeypatch)

    def _slow_embed(*args, **kwargs):
        time.sleep(0.5)
        return np.array([1.0])

    monkeypatch.setattr(embeddings, "embed_segment", _slow_embed)
    _make_video_with_segment(client, tmp_path)

    first = client.post("/api/analysis/run")
    assert first.status_code == 202

    second = client.post("/api/analysis/run")
    assert second.status_code == 409

    _poll_until_done(client)

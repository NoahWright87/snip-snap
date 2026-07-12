import json

from app.store import SIDECAR_NAME


def _make_video(client, tmp_path, name="clip.mp4"):
    folder = tmp_path / "library"
    folder.mkdir(exist_ok=True)
    (folder / name).write_bytes(b"x")
    client.post("/api/videos/ingest", json={"folder": str(folder)})
    videos = {v["filename"]: v for v in client.get("/api/videos").json()}
    return folder, videos[name]["id"]


def test_ingest_writes_a_sidecar_json_in_the_folder(client, tmp_path):
    folder, video_id = _make_video(client, tmp_path)

    sidecar = folder / SIDECAR_NAME
    assert sidecar.is_file()

    data = json.loads(sidecar.read_text())
    assert video_id in data["videos"]
    assert data["videos"][video_id]["filename"] == "clip.mp4"


def test_sidecar_is_updated_after_segment_edits(client, tmp_path):
    folder, video_id = _make_video(client, tmp_path)
    client.post(f"/api/videos/{video_id}/segments/split", json={"time": 4, "duration": 10})

    data = json.loads((folder / SIDECAR_NAME).read_text())
    assert len(data["videos"][video_id]["segments"]) == 2


def test_data_survives_a_fresh_process_reading_the_same_folder(client, tmp_path):
    """The whole point: point a second "session" at the same folder (no
    shared in-memory state) and the segments/tags should still be there,
    because they live in the folder's JSON, not just in memory."""
    folder, video_id = _make_video(client, tmp_path)
    client.post(f"/api/videos/{video_id}/segments/split", json={"time": 4, "duration": 10})
    segment_id = client.get(f"/api/videos/{video_id}/segments").json()[0]["id"]
    client.post(f"/api/segments/{segment_id}/tags", json={"tag": "boring"})

    # Simulate a fresh look at the same folder from scratch.
    from app.store import read_folder_data

    data = read_folder_data(folder)
    segments = data["videos"][video_id]["segments"]
    tagged = [s for s in segments if s["tags"]]
    assert tagged and tagged[0]["tags"] == ["boring"]

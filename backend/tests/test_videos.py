def test_ingest_registers_video_files(client, tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"not a real video, just needs the right extension")
    (folder / "notes.txt").write_text("ignored, not a video extension")

    resp = client.post("/api/videos/ingest", json={"folder": str(folder)})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["added"]) == 1
    assert body["skipped_existing"] == 0

    videos = client.get("/api/videos").json()
    assert len(videos) == 1
    assert videos[0]["filename"] == "clip.mp4"
    assert videos[0]["status"] == "unprocessed"
    assert videos[0]["segment_count"] == 0


def test_ingest_does_not_recurse_into_subfolders(client, tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"x")
    edited = folder / "edited"
    edited.mkdir()
    (edited / "clip_edited.mp4").write_bytes(b"x")

    resp = client.post("/api/videos/ingest", json={"folder": str(folder)})
    assert resp.json()["added"] == [client.get("/api/videos").json()[0]["id"]]
    assert len(client.get("/api/videos").json()) == 1


def test_ingest_is_idempotent(client, tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"x")

    client.post("/api/videos/ingest", json={"folder": str(folder)})
    resp = client.post("/api/videos/ingest", json={"folder": str(folder)})

    assert resp.json() == {"added": [], "skipped_existing": 1}
    assert len(client.get("/api/videos").json()) == 1


def test_ingest_rejects_missing_folder(client, tmp_path):
    resp = client.post("/api/videos/ingest", json={"folder": str(tmp_path / "nope")})
    assert resp.status_code == 400


def test_get_video_404(client):
    assert client.get("/api/videos/999").status_code == 404


def test_pair_videos(client, tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    (folder / "raw.mp4").write_bytes(b"x")
    (folder / "edited.mp4").write_bytes(b"x")
    client.post("/api/videos/ingest", json={"folder": str(folder)})
    videos = {v["filename"]: v for v in client.get("/api/videos").json()}

    raw_id = videos["raw.mp4"]["id"]
    edited_id = videos["edited.mp4"]["id"]

    resp = client.post(
        f"/api/videos/{raw_id}/pair",
        json={"paired_video_id": edited_id, "source_type": "raw"},
    )
    assert resp.status_code == 200
    assert resp.json()["source_type"] == "raw"
    assert resp.json()["paired_video_id"] == edited_id


def test_stream_missing_file_404(client, tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    video_path = folder / "clip.mp4"
    video_path.write_bytes(b"x")
    client.post("/api/videos/ingest", json={"folder": str(folder)})
    video_id = client.get("/api/videos").json()[0]["id"]

    video_path.unlink()

    resp = client.get(f"/api/videos/{video_id}/stream")
    assert resp.status_code == 404


def test_stream_range_request(client, tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"0123456789")
    client.post("/api/videos/ingest", json={"folder": str(folder)})
    video_id = client.get("/api/videos").json()[0]["id"]

    resp = client.get(f"/api/videos/{video_id}/stream", headers={"Range": "bytes=2-5"})
    assert resp.status_code == 206
    assert resp.content == b"2345"
    assert resp.headers["content-range"] == "bytes 2-5/10"

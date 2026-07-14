def test_list_folders_reflects_ingested_folders_and_video_counts(client, tmp_path):
    folder_a = tmp_path / "a"
    folder_a.mkdir()
    (folder_a / "clip.mp4").write_bytes(b"x")
    folder_b = tmp_path / "b"
    folder_b.mkdir()

    client.post("/api/videos/ingest", json={"folder": str(folder_a)})
    client.post("/api/videos/ingest", json={"folder": str(folder_b)})

    folders = {f["path"]: f for f in client.get("/api/folders").json()}
    assert folders[str(folder_a)]["video_count"] == 1
    assert folders[str(folder_b)]["video_count"] == 0


def test_remove_folder_drops_it_from_the_registry(client, tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"x")
    client.post("/api/videos/ingest", json={"folder": str(folder)})

    folder_id = client.get("/api/folders").json()[0]["id"]
    resp = client.delete(f"/api/folders/{folder_id}")
    assert resp.status_code == 204
    assert client.get("/api/folders").json() == []

    # The videos "disappear" from the library view (no registered folder to
    # find them through) but nothing on disk was touched.
    assert client.get("/api/videos").json() == []
    assert (folder / ".snipsnap.json").is_file()
    assert (folder / "clip.mp4").is_file()


def test_remove_folder_404s_for_unknown_id(client):
    resp = client.delete("/api/folders/999")
    assert resp.status_code == 404


def test_re_adding_a_removed_folder_recovers_its_data(client, tmp_path):
    folder = tmp_path / "library"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"x")
    client.post("/api/videos/ingest", json={"folder": str(folder)})
    video_id = client.get("/api/videos").json()[0]["id"]
    client.post(f"/api/videos/{video_id}/segments/init", json={"duration": 10})
    client.post(f"/api/segments/{client.get(f'/api/videos/{video_id}/segments').json()[0]['id']}/tags", json={"tag": "boring"})

    folder_id = client.get("/api/folders").json()[0]["id"]
    client.delete(f"/api/folders/{folder_id}")

    client.post("/api/videos/ingest", json={"folder": str(folder)})
    videos = client.get("/api/videos").json()
    assert len(videos) == 1
    assert videos[0]["id"] == video_id
    segments = client.get(f"/api/videos/{video_id}/segments").json()
    assert segments[0]["tags"] == ["boring"]

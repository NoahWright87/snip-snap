def _make_video(client, tmp_path, name="clip.mp4"):
    folder = tmp_path / "library"
    folder.mkdir(exist_ok=True)
    (folder / name).write_bytes(b"x")
    client.post("/api/videos/ingest", json={"folder": str(folder)})
    videos = {v["filename"]: v for v in client.get("/api/videos").json()}
    return videos[name]["id"]


def test_create_and_list_segments(client, tmp_path):
    video_id = _make_video(client, tmp_path)

    resp = client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 5, "decision": "cut", "tag": "structural_intro"},
    )
    assert resp.status_code == 201
    segment = resp.json()
    assert segment["decision"] == "cut"
    assert segment["tag"] == "structural_intro"
    assert segment["provenance"] == "manual"

    segments = client.get(f"/api/videos/{video_id}/segments").json()
    assert len(segments) == 1

    video = client.get(f"/api/videos/{video_id}").json()
    assert video["segment_count"] == 1
    assert video["status"] == "in_progress"


def test_create_segment_rejects_bad_range(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    resp = client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 5, "end_time": 5, "decision": "keep"},
    )
    assert resp.status_code == 400


def test_update_segment(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    segment = client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 5, "decision": "cut"},
    ).json()

    resp = client.patch(f"/api/segments/{segment['id']}", json={"tag": "feet"})
    assert resp.status_code == 200
    assert resp.json()["tag"] == "feet"


def test_delete_segment(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    segment = client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 5, "decision": "cut"},
    ).json()

    resp = client.delete(f"/api/segments/{segment['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/videos/{video_id}/segments").json() == []


def test_list_tags_is_distinct_and_sorted(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    for tag in ["feet", "closeup", "feet"]:
        client.post(
            f"/api/videos/{video_id}/segments",
            json={"start_time": 0, "end_time": 1, "decision": "cut", "tag": tag},
        )

    resp = client.get("/api/tags")
    assert resp.json() == ["closeup", "feet"]

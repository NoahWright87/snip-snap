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
        json={"start_time": 0, "end_time": 5, "decision": "cut", "tags": ["structural_intro"]},
    )
    assert resp.status_code == 201
    segment = resp.json()
    assert segment["decision"] == "cut"
    assert segment["tags"] == ["structural_intro"]
    assert segment["provenance"] == "manual"

    segments = client.get(f"/api/videos/{video_id}/segments").json()
    assert len(segments) == 1

    video = client.get(f"/api/videos/{video_id}").json()
    assert video["segment_count"] == 1
    assert video["status"] == "in_progress"


def test_create_segment_defaults_to_keep_with_no_tags(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    resp = client.post(f"/api/videos/{video_id}/segments", json={"start_time": 0, "end_time": 5})
    assert resp.status_code == 201
    assert resp.json()["decision"] == "keep"
    assert resp.json()["tags"] == []


def test_create_segment_rejects_bad_range(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    resp = client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 5, "end_time": 5},
    )
    assert resp.status_code == 400


def test_update_segment_decision(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    segment = client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 5},
    ).json()

    resp = client.patch(f"/api/segments/{segment['id']}", json={"decision": "cut"})
    assert resp.status_code == 200
    assert resp.json()["decision"] == "cut"


def test_delete_segment(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    segment = client.post(
        f"/api/videos/{video_id}/segments",
        json={"start_time": 0, "end_time": 5, "decision": "cut"},
    ).json()

    resp = client.delete(f"/api/segments/{segment['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/videos/{video_id}/segments").json() == []


def test_add_and_remove_tags(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    segment = client.post(f"/api/videos/{video_id}/segments", json={"start_time": 0, "end_time": 5}).json()

    resp = client.post(f"/api/segments/{segment['id']}/tags", json={"tag": "feet"})
    assert resp.status_code == 200
    assert resp.json()["tags"] == ["feet"]

    resp = client.post(f"/api/segments/{segment['id']}/tags", json={"tag": "closeup"})
    assert resp.json()["tags"] == ["closeup", "feet"]

    # Adding the same tag twice is a no-op, not a duplicate.
    resp = client.post(f"/api/segments/{segment['id']}/tags", json={"tag": "feet"})
    assert resp.json()["tags"] == ["closeup", "feet"]

    resp = client.delete(f"/api/segments/{segment['id']}/tags/feet")
    assert resp.status_code == 200
    assert resp.json()["tags"] == ["closeup"]


def test_add_tag_rejects_empty(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    segment = client.post(f"/api/videos/{video_id}/segments", json={"start_time": 0, "end_time": 5}).json()
    resp = client.post(f"/api/segments/{segment['id']}/tags", json={"tag": "   "})
    assert resp.status_code == 400


def test_list_tags_is_distinct_and_sorted(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    segment = client.post(f"/api/videos/{video_id}/segments", json={"start_time": 0, "end_time": 1}).json()
    for tag in ["feet", "closeup", "feet"]:
        client.post(f"/api/segments/{segment['id']}/tags", json={"tag": tag})

    resp = client.get("/api/tags")
    assert resp.json() == ["closeup", "feet"]


def test_init_segments_seeds_one_full_length_keep_segment(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    resp = client.post(f"/api/videos/{video_id}/segments/init", json={"duration": 10})
    assert resp.status_code == 200
    segments = resp.json()
    assert len(segments) == 1
    assert segments[0]["start_time"] == 0
    assert segments[0]["end_time"] == 10
    assert segments[0]["decision"] == "keep"


def test_init_segments_is_idempotent(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    client.post(f"/api/videos/{video_id}/segments/init", json={"duration": 10})
    resp = client.post(f"/api/videos/{video_id}/segments/init", json={"duration": 10})
    assert len(resp.json()) == 1


def test_split_auto_seeds_then_splits(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    # No init call first - split should seed the full-length segment itself.
    resp = client.post(f"/api/videos/{video_id}/segments/split", json={"time": 4, "duration": 10})
    assert resp.status_code == 200
    segments = sorted(resp.json(), key=lambda s: s["start_time"])
    assert len(segments) == 2
    assert segments[0]["start_time"] == 0 and segments[0]["end_time"] == 4
    assert segments[1]["start_time"] == 4 and segments[1]["end_time"] == 10


def test_split_inherits_decision_and_tags(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    client.post(f"/api/videos/{video_id}/segments/init", json={"duration": 10})
    segment = client.get(f"/api/videos/{video_id}/segments").json()[0]
    client.patch(f"/api/segments/{segment['id']}", json={"decision": "cut"})
    client.post(f"/api/segments/{segment['id']}/tags", json={"tag": "boring"})

    resp = client.post(f"/api/videos/{video_id}/segments/split", json={"time": 4, "duration": 10})
    for seg in resp.json():
        assert seg["decision"] == "cut"
        assert seg["tags"] == ["boring"]


def test_split_again_further_subdivides(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    client.post(f"/api/videos/{video_id}/segments/split", json={"time": 4, "duration": 10})
    resp = client.post(f"/api/videos/{video_id}/segments/split", json={"time": 7, "duration": 10})
    segments = sorted(resp.json(), key=lambda s: s["start_time"])
    assert [(s["start_time"], s["end_time"]) for s in segments] == [(0, 4), (4, 7), (7, 10)]


def test_split_rejects_point_outside_any_segment(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    resp = client.post(f"/api/videos/{video_id}/segments/split", json={"time": 15, "duration": 10})
    assert resp.status_code == 400


def test_split_rejects_point_too_close_to_boundary(client, tmp_path):
    video_id = _make_video(client, tmp_path)
    client.post(f"/api/videos/{video_id}/segments/split", json={"time": 4, "duration": 10})
    resp = client.post(f"/api/videos/{video_id}/segments/split", json={"time": 4.001, "duration": 10})
    assert resp.status_code == 400

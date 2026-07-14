def test_open_file_launches_the_default_app(client, tmp_path, monkeypatch):
    target = tmp_path / "clip_edited.mp4"
    target.write_bytes(b"x")

    calls = []
    monkeypatch.setattr("app.main.open_file", lambda path: calls.append(path))

    resp = client.post("/api/open-file", json={"path": str(target)})
    assert resp.status_code == 200
    assert calls == [str(target)]


def test_open_file_404s_for_missing_file(client, tmp_path):
    resp = client.post("/api/open-file", json={"path": str(tmp_path / "nope.mp4")})
    assert resp.status_code == 404


def test_open_file_reports_failure_cleanly(client, tmp_path, monkeypatch):
    target = tmp_path / "clip_edited.mp4"
    target.write_bytes(b"x")

    def boom(path):
        raise OSError("no association")

    monkeypatch.setattr("app.main.open_file", boom)
    resp = client.post("/api/open-file", json={"path": str(target)})
    assert resp.status_code == 500

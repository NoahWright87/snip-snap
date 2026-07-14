def test_pick_folder_returns_selected_path(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.routes.dialogs._ask_directory", lambda initial_dir: str(tmp_path))
    resp = client.post("/api/dialogs/pick-folder", json={})
    assert resp.status_code == 200
    assert resp.json() == {"path": str(tmp_path)}


def test_pick_folder_returns_null_path_when_cancelled(client, monkeypatch):
    monkeypatch.setattr("app.routes.dialogs._ask_directory", lambda initial_dir: None)
    resp = client.post("/api/dialogs/pick-folder", json={})
    assert resp.status_code == 200
    assert resp.json() == {"path": None}


def test_pick_folder_falls_back_to_home_for_bad_initial_dir(client, tmp_path, monkeypatch):
    seen = {}

    def fake_ask(initial_dir):
        seen["initial_dir"] = initial_dir
        return None

    monkeypatch.setattr("app.routes.dialogs._ask_directory", fake_ask)
    resp = client.post("/api/dialogs/pick-folder", json={"initial_dir": str(tmp_path / "nonexistent")})
    assert resp.status_code == 200
    assert seen["initial_dir"] != str(tmp_path / "nonexistent")


def test_pick_folder_uses_valid_initial_dir(client, tmp_path, monkeypatch):
    seen = {}

    def fake_ask(initial_dir):
        seen["initial_dir"] = initial_dir
        return None

    monkeypatch.setattr("app.routes.dialogs._ask_directory", fake_ask)
    client.post("/api/dialogs/pick-folder", json={"initial_dir": str(tmp_path)})
    assert seen["initial_dir"] == str(tmp_path)


def test_pick_folder_reports_unavailable_when_underlying_call_fails(client, monkeypatch):
    def boom(initial_dir):
        raise RuntimeError("no display")

    monkeypatch.setattr("app.routes.dialogs._ask_directory", boom)
    resp = client.post("/api/dialogs/pick-folder", json={})
    assert resp.status_code == 501
    assert "unavailable" in resp.json()["detail"]


def test_pick_save_file_returns_selected_path(client, monkeypatch):
    monkeypatch.setattr(
        "app.routes.dialogs._ask_save_file", lambda initial_dir, initial_file: "/videos/edited/clip_edited.mp4"
    )
    resp = client.post("/api/dialogs/pick-save-file", json={"initial_file": "clip_edited.mp4"})
    assert resp.status_code == 200
    assert resp.json() == {"path": "/videos/edited/clip_edited.mp4"}


def test_pick_save_file_passes_default_filename(client, monkeypatch):
    seen = {}

    def fake_ask(initial_dir, initial_file):
        seen["initial_file"] = initial_file
        return None

    monkeypatch.setattr("app.routes.dialogs._ask_save_file", fake_ask)
    client.post("/api/dialogs/pick-save-file", json={})
    assert seen["initial_file"] == "export.mp4"

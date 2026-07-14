import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

from app import config, db, ffmpeg_setup
from app.routes import export as export_routes


@pytest.fixture(autouse=True)
def _reset_ffmpeg_status():
    # ffmpeg_setup._status is module-level global state that would otherwise
    # leak between tests regardless of whether they use the `client` fixture.
    ffmpeg_setup._set_status("checking", "")
    yield
    ffmpeg_setup._set_status("checking", "")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    # Tests shouldn't trigger a real ffmpeg download (slow, network-dependent,
    # and would run on every single test's TestClient startup). Tests that
    # care about ffmpeg behavior monkeypatch it explicitly.
    monkeypatch.setattr("app.main.ensure_ffmpeg_ready", lambda: None)

    # Export job state is a module-level dict so it survives across tests
    # in the same process - reset it for isolation.
    export_routes._jobs.clear()

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

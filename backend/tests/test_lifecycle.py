from urllib.error import URLError

from app import lifecycle
from app.version import LatestRelease


def test_seconds_since_heartbeat_resets_on_record():
    lifecycle.record_heartbeat()
    assert lifecycle.seconds_since_heartbeat() < 1


def test_health_endpoint(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_heartbeat_endpoint_calls_record_heartbeat(client, monkeypatch):
    calls = []
    monkeypatch.setattr("app.main.record_heartbeat", lambda: calls.append(True))
    resp = client.post("/api/heartbeat")
    assert resp.status_code == 200
    assert calls == [True]


def test_shutdown_endpoint_calls_request_shutdown(client, monkeypatch):
    calls = []
    monkeypatch.setattr("app.main.request_shutdown", lambda *a, **kw: calls.append(True))
    resp = client.post("/api/shutdown")
    assert resp.status_code == 200
    assert calls == [True]


def test_update_status_endpoint_reports_available_update(client, monkeypatch):
    monkeypatch.setattr("app.main.get_current_version", lambda: "1.2.3")
    monkeypatch.setattr(
        "app.main.fetch_latest_release",
        lambda: LatestRelease(version="1.2.4", html_url="https://example.test/release"),
    )
    resp = client.get("/api/app/update-status")
    assert resp.status_code == 200
    assert resp.json() == {
        "current_version": "1.2.3",
        "latest_version": "1.2.4",
        "update_available": True,
        "release_url": "https://example.test/release",
        "error": None,
    }


def test_update_status_endpoint_no_update(client, monkeypatch):
    monkeypatch.setattr("app.main.get_current_version", lambda: "1.2.3")
    monkeypatch.setattr(
        "app.main.fetch_latest_release",
        lambda: LatestRelease(version="1.2.3", html_url="https://example.test/release"),
    )
    resp = client.get("/api/app/update-status")
    assert resp.status_code == 200
    assert resp.json()["update_available"] is False


def test_update_status_endpoint_handles_release_lookup_errors(client, monkeypatch):
    monkeypatch.setattr("app.main.get_current_version", lambda: "1.2.3")

    def _raise():
        raise URLError("no network")

    monkeypatch.setattr("app.main.fetch_latest_release", _raise)
    resp = client.get("/api/app/update-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_version"] == "1.2.3"
    assert body["latest_version"] is None
    assert body["update_available"] is False
    assert body["release_url"] == "https://github.com/NoahWright87/snip-snap/releases/latest"
    assert "no network" in body["error"]

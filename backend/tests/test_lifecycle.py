from app import lifecycle


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

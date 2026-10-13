"""RED: readiness contract (liveness vs readiness split).

Seam: HTTP GET /ready. Probes are monkeypatched at the module seam
(app.api.ready.probe_database / probe_redis) — never internals.
"""

from fastapi.testclient import TestClient

import app.api.ready as ready_module
from app.main import app


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


async def _up() -> str:
    return "up"


async def _down() -> str:
    return "down"


def test_ready_up_when_backends_healthy(monkeypatch) -> None:
    monkeypatch.setattr(ready_module, "probe_database", _up)
    monkeypatch.setattr(ready_module, "probe_redis", _up)
    response = _client().get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"db": "up", "redis": "up"}}


def test_ready_503_identifies_database_down(monkeypatch) -> None:
    monkeypatch.setattr(ready_module, "probe_database", _down)
    monkeypatch.setattr(ready_module, "probe_redis", _up)
    response = _client().get("/ready")
    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["checks"]["db"] == "down"
    assert body["checks"]["redis"] == "up"


def test_ready_503_identifies_redis_down(monkeypatch) -> None:
    monkeypatch.setattr(ready_module, "probe_database", _up)
    monkeypatch.setattr(ready_module, "probe_redis", _down)
    response = _client().get("/ready")
    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["checks"]["db"] == "up"
    assert body["checks"]["redis"] == "down"


def test_ready_503_when_both_down(monkeypatch) -> None:
    monkeypatch.setattr(ready_module, "probe_database", _down)
    monkeypatch.setattr(ready_module, "probe_redis", _down)
    response = _client().get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["checks"] == {"db": "down", "redis": "down"}


def test_ready_rejects_undeclared_query_param() -> None:
    response = _client().get("/ready", params={"unexpected_field": "1"})
    assert response.status_code == 422

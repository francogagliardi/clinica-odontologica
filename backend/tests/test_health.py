"""RED: baseline liveness contract.

Seam: HTTP GET /health (public boundary).
Spec: 200 {"status": "ok", "service": "api"} even with db+redis down;
unknown query params are rejected with 422 (extra=forbid boundary rule).
"""

from fastapi.testclient import TestClient

from app.main import app


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_health_returns_ok_without_dependencies(monkeypatch) -> None:
    """Liveness must not touch the network, even with bogus backends."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://nope:nope@127.0.0.1:1/nope")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def test_health_values_come_from_spec_literals() -> None:
    """Response shape matches the spec scenario literal, not code-derived."""
    response = _client().get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "api"
    assert set(body.keys()) == {"status", "service"}


def test_health_rejects_undeclared_query_param() -> None:
    """Undeclared fields at the boundary are rejected (RORO/extra=forbid)."""
    response = _client().get("/health", params={"unexpected_field": "1"})
    assert response.status_code == 422

"""RED: SPA <-> API cross-origin contract (C-01 fix found in manual review).

Seam: HTTP boundary with the `Origin` header a browser sends from the SPA
(http://127.0.0.1:8080) to the API (http://127.0.0.1:8000).

Why this exists: the SPA runs on a different origin than the API, so without
CORS the browser blocks every fetch with status 0 ("Failed to fetch") even
though the endpoint answers 200 to curl. Mocked component tests cannot catch
this, so the guard must live at the HTTP boundary.
"""

from fastapi.testclient import TestClient

from app.main import app

SPA_ORIGIN = "http://127.0.0.1:8080"


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_health_allows_spa_origin() -> None:
    """Simple request from the SPA origin carries the allow-origin header."""
    response = _client().get("/health", headers={"Origin": SPA_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == SPA_ORIGIN


def test_preflight_allows_spa_get() -> None:
    """Preflight for GET /ready succeeds and advertises the method."""
    response = _client().options(
        "/ready",
        headers={
            "Origin": SPA_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == SPA_ORIGIN
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_unknown_origin_is_not_reflected() -> None:
    """Only configured origins are allowed (no wildcard reflection)."""
    response = _client().get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers

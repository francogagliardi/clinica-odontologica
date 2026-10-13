"""Shared FastAPI dependencies (DI seam, R-02).

C-01 exposes settings access + the strict-boundary guard. Auth/RBAC
dependencies (current user, role guards) land here in C-03.
"""

from functools import lru_cache

from fastapi import HTTPException, Request

from app.core.settings import Settings, load_settings


@lru_cache
def get_settings() -> Settings:
    """Process-cached settings (fail-fast on missing secrets at first use)."""
    return load_settings()


async def reject_unexpected_query(request: Request) -> None:
    """Strict boundary: baseline GET endpoints declare no params (422 otherwise).

    Enforces the RORO/extra=forbid rule for endpoints without a body: any
    undeclared query field is rejected instead of silently ignored.
    """
    if request.query_params:
        raise HTTPException(
            status_code=422, detail="Unexpected query parameters"
        )

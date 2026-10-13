"""Liveness probe: 200 without touching any dependency (R-02: async, typed)."""

from fastapi import APIRouter, Depends

from app.api.deps import reject_unexpected_query
from app.schemas.system import HealthResponse

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe (no dependency I/O)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def get_health() -> HealthResponse:
    """Return ok even when PostgreSQL/Redis are down (orchestrator-safe)."""
    return HealthResponse(status="ok", service="api")

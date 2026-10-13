"""RORO boundary schemas for the baseline system endpoints (R-01: extra='forbid')."""

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Liveness payload — exact shape from the spec scenario."""

    model_config = ConfigDict(extra="forbid")

    status: str
    service: str


class ReadinessChecks(BaseModel):
    """Per-dependency state; 'down' values identify the failing dependency."""

    model_config = ConfigDict(extra="forbid")

    db: str
    redis: str


class ReadinessResponse(BaseModel):
    """Readiness payload, shared by the 200 and the 503 bodies."""

    model_config = ConfigDict(extra="forbid")

    status: str
    checks: ReadinessChecks

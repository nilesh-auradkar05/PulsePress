"""Health-check route — internal operability endpoint (S1-T02).

No authentication; returns static JSON. Mounted at the root path (not under
the product `/v1` prefix) so it can serve as the ALB health-check target.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse, tags=["internal"])
def healthz() -> HealthResponse:
    return HealthResponse(
        service=settings.service_name,
        version=settings.version,
        status="ok",
    )

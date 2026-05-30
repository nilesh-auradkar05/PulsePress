"""Internal health-check schema.

This endpoint is intentionally NOT part of the product HTTP contract
(`docs/openapi.yaml`). It is an internal operability endpoint used as the ALB
health-check target (sprint-plan S1-T02, ADR-0006), so its shape lives here in
code rather than in the public OpenAPI surface.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: str
    version: str
    status: Literal["ok"] = "ok"

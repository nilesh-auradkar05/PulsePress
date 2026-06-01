"""User response schema (mirrors the OpenAPI ``User`` schema)."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    email: str | None = None
    is_admin: bool
    created_at: datetime.datetime

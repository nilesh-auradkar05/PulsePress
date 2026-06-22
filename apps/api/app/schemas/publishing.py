"""Publishing API schemas."""

from __future__ import annotations

import datetime
import uuid
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class PublicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_user_id: uuid.UUID
    handle: str
    name: str
    description: str | None = None
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PublicationCreate(BaseModel):
    handle: str = Field(min_length=3, max_length=32, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("handle", mode="before")
    @classmethod
    def normalize_handle(cls, value: object) -> str:
        return str(value).strip().lower()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name must not be blank")
        return normalized


class PublicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    avatar_url: HttpUrl | None = None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one publication field must be provided")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name must not be null")
        return self


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    publication_id: uuid.UUID
    name: str
    monthly_price_cents: int
    currency: str
    allow_open_amount: bool
    benefits: list[str] | None = None
    is_active: bool


class PublicationDetail(PublicationOut):
    active_plans: list[PlanOut] = Field(default_factory=list)


class PublicationList(BaseModel):
    items: list[PublicationOut]
    next_cursor: str | None = None


class PublicationSummary(BaseModel):
    publication_id: uuid.UUID
    subscriber_count: int = Field(ge=0)
    post_count: int = Field(ge=0)
    recent_revenue_cents: int = Field(default=0, ge=0)
    generated_at: datetime.datetime


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    publication_id: uuid.UUID
    author_user_id: uuid.UUID
    title: str
    slug: str
    status: Literal["draft", "published", "archived"]
    visibility: Literal["free", "paid"]
    published_at: datetime.datetime | None = None
    archived_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PostRead(PostOut):
    body: str | None
    entitled: bool


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    visibility: Literal["free", "paid"] = "free"

    @field_validator("title", "body")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text must not be blank")
        return normalized


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1)
    visibility: Literal["free", "paid"] | None = None

    @field_validator("title", "body")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one post field must be provided")
        for field in ("title", "body", "visibility"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class PostList(BaseModel):
    items: list[PostOut]
    next_cursor: str | None = None


class PostPublishResult(BaseModel):
    post_id: uuid.UUID
    status: Literal["published"]
    published_at: datetime.datetime
    version_id: uuid.UUID
    newsletter_status: Literal["queued", "already_processed"]

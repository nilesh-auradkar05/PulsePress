"""Publishing context (content-shaped)."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

POST_STATUSES = ("draft", "published", "archived")
POST_VISIBILITIES = ("free", "paid")
NEWSLETTER_STATUSES = ("requested", "sent", "failed")


class Publication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "publications"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    handle: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class Post(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint(
            f"status IN {POST_STATUSES}", name="status_valid"
        ),
        CheckConstraint(
            f"visibility IN {POST_VISIBILITIES}", name="visibility_valid"
        ),
    )

    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id"), index=True, nullable=False
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    slug: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="free")
    published_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class PostVersion(UUIDPrimaryKeyMixin, Base):
    """Immutable snapshot written at publish time; the newsletter renders from this."""

    __tablename__ = "post_versions"

    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posts.id"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshotted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NewsletterSend(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "newsletter_sends"
    __table_args__ = (
        CheckConstraint(f"status IN {NEWSLETTER_STATUSES}", name="status_valid"),
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posts.id"), index=True, nullable=False
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="requested")
    recipient_count_sim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    artifact_s3_key: Mapped[str | None] = mapped_column(String(1024))
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

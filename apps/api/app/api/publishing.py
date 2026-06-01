"""Publication and post API routes."""

from __future__ import annotations

import datetime
import re
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_session
from app.models import OutboxEvent, Post, PostVersion, Publication, User
from app.schemas.publishing import (
    PostCreate,
    PostList,
    PostOut,
    PostPublishResult,
    PostRead,
    PostUpdate,
    PublicationCreate,
    PublicationDetail,
    PublicationList,
    PublicationOut,
    PublicationUpdate,
)

router = APIRouter(prefix="/v1", tags=["publishing"])

DbSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:80].strip("-") or "post"


def _unique_slug(db: Session, *, publication_id: uuid.UUID, title: str) -> str:
    base = _slugify(title)
    slug = base
    suffix = 2

    while db.execute(
        select(Post.id).where(Post.publication_id == publication_id, Post.slug == slug)
    ).first():
        suffix_text = f"-{suffix}"
        slug = f"{base[: 80 - len(suffix_text)]}{suffix_text}"
        suffix += 1

    return slug


def _get_publication(db: Session, publication_id: uuid.UUID) -> Publication:
    publication = db.get(Publication, publication_id)
    if publication is None or not publication.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication not found")
    return publication


def _get_post(db: Session, post_id: uuid.UUID) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


def _ensure_publication_owner(publication: Publication, user: User) -> None:
    if publication.owner_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the publication owner can perform this action",
        )


def _ensure_post_owner(post: Post, user: User) -> None:
    if post.author_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the post owner can perform this action",
        )


def _post_read_response(post: Post, user: User) -> PostRead:
    entitled = post.author_user_id == user.id or post.visibility == "free"
    return PostRead(
        id=post.id,
        publication_id=post.publication_id,
        author_user_id=post.author_user_id,
        title=post.title,
        slug=post.slug,
        status=post.status,  # type: ignore[arg-type]
        visibility=post.visibility,  # type: ignore[arg-type]
        published_at=post.published_at,
        archived_at=post.archived_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
        body=post.body if entitled else None,
        entitled=entitled,
    )


@router.get("/publications", response_model=PublicationList)
def list_publications(
    db: DbSession,
    current_user: CurrentUser,
    owner: Annotated[Literal["me"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> PublicationList:
    del cursor
    stmt = (
        select(Publication)
        .where(Publication.is_active.is_(True))
        .order_by(Publication.created_at.desc(), Publication.id.desc())
        .limit(limit)
    )
    if owner == "me":
        stmt = stmt.where(Publication.owner_user_id == current_user.id)

    items = db.execute(stmt).scalars().all()
    return PublicationList(items=[PublicationOut.model_validate(item) for item in items])


@router.post(
    "/publications",
    response_model=PublicationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_publication(
    body: PublicationCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PublicationOut:
    existing = db.execute(
        select(Publication.id).where(Publication.handle == body.handle)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Handle already in use")

    publication = Publication(
        owner_user_id=current_user.id,
        handle=body.handle,
        name=body.name,
        description=body.description,
        is_active=True,
    )
    db.add(publication)
    db.commit()
    db.refresh(publication)
    return PublicationOut.model_validate(publication)


@router.get("/publications/{publication_id}", response_model=PublicationDetail)
def get_publication(
    publication_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> PublicationDetail:
    del current_user
    publication = _get_publication(db, publication_id)
    return PublicationDetail(**PublicationOut.model_validate(publication).model_dump())


@router.patch("/publications/{publication_id}", response_model=PublicationOut)
def update_publication(
    publication_id: uuid.UUID,
    body: PublicationUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> PublicationOut:
    publication = _get_publication(db, publication_id)
    _ensure_publication_owner(publication, current_user)

    fields_set = body.model_fields_set
    if "name" in fields_set and body.name is not None:
        publication.name = body.name
    if "description" in fields_set:
        publication.description = body.description
    if "avatar_url" in fields_set:
        publication.avatar_url = str(body.avatar_url) if body.avatar_url is not None else None

    db.commit()
    db.refresh(publication)
    return PublicationOut.model_validate(publication)


@router.get("/publications/{publication_id}/posts", response_model=PostList)
def list_posts(
    publication_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Annotated[
        Literal["draft", "published", "archived"] | None,
        Query(alias="status"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> PostList:
    del cursor
    publication = _get_publication(db, publication_id)
    is_owner = publication.owner_user_id == current_user.id

    stmt = (
        select(Post)
        .where(Post.publication_id == publication_id)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .limit(limit)
    )
    if status_filter is not None:
        stmt = stmt.where(Post.status == status_filter)
    elif not is_owner:
        stmt = stmt.where(Post.status == "published")

    if not is_owner:
        stmt = stmt.where(Post.status == "published")

    items = db.execute(stmt).scalars().all()
    return PostList(items=[PostOut.model_validate(item) for item in items])


@router.post(
    "/publications/{publication_id}/posts",
    response_model=PostOut,
    status_code=status.HTTP_201_CREATED,
)
def create_post(
    publication_id: uuid.UUID,
    body: PostCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PostOut:
    publication = _get_publication(db, publication_id)
    _ensure_publication_owner(publication, current_user)

    post = Post(
        publication_id=publication.id,
        author_user_id=current_user.id,
        title=body.title,
        slug=_unique_slug(db, publication_id=publication.id, title=body.title),
        body=body.body,
        status="draft",
        visibility=body.visibility,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return PostOut.model_validate(post)


@router.get("/posts/{post_id}", response_model=PostRead)
def get_post(post_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> PostRead:
    post = _get_post(db, post_id)
    if post.status == "archived" and post.author_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.status == "draft" and post.author_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return _post_read_response(post, current_user)


@router.patch("/posts/{post_id}", response_model=PostOut)
def update_post(
    post_id: uuid.UUID,
    body: PostUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> PostOut:
    post = _get_post(db, post_id)
    _ensure_post_owner(post, current_user)
    if post.status == "archived":
        raise HTTPException(status_code=422, detail="Archived posts cannot be edited")

    fields_set = body.model_fields_set
    if "title" in fields_set and body.title is not None:
        post.title = body.title
    if "body" in fields_set and body.body is not None:
        post.body = body.body
    if "visibility" in fields_set and body.visibility is not None:
        post.visibility = body.visibility

    db.commit()
    db.refresh(post)
    return PostOut.model_validate(post)


@router.delete("/posts/{post_id}", response_model=PostOut)
def archive_post(post_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> PostOut:
    post = _get_post(db, post_id)
    _ensure_post_owner(post, current_user)

    if post.status != "archived":
        post.status = "archived"
        post.archived_at = _utcnow()
        db.commit()
        db.refresh(post)

    return PostOut.model_validate(post)


@router.post("/posts/{post_id}/publish", response_model=PostPublishResult)
def publish_post(
    post_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> PostPublishResult:
    post = _get_post(db, post_id)
    _ensure_post_owner(post, current_user)

    if post.status == "archived":
        raise HTTPException(status_code=422, detail="Archived posts cannot be published")

    existing_version = db.execute(
        select(PostVersion).where(PostVersion.post_id == post.id).limit(1)
    ).scalar_one_or_none()
    if post.status == "published" and existing_version is not None:
        return PostPublishResult(
            post_id=post.id,
            status="published",
            published_at=post.published_at or existing_version.snapshotted_at,
            version_id=existing_version.id,
            newsletter_status="already_processed",
        )

    now = _utcnow()
    post.status = "published"
    published_at = post.published_at or now
    post.published_at = published_at

    version = existing_version or PostVersion(
        post_id=post.id,
        title=post.title,
        body=post.body,
        visibility=post.visibility,
    )
    if existing_version is None:
        db.add(version)
        db.flush()

    event_exists = db.execute(
        select(OutboxEvent.id).where(
            OutboxEvent.aggregate_type == "post",
            OutboxEvent.aggregate_id == post.id,
            OutboxEvent.event_type == "post.published",
        )
    ).scalar_one_or_none()
    if event_exists is None:
        db.add(
            OutboxEvent(
                aggregate_type="post",
                aggregate_id=post.id,
                event_type="post.published",
                event_version=1,
                payload={
                    "post_id": str(post.id),
                    "publication_id": str(post.publication_id),
                    "version_id": str(version.id),
                    "visibility": post.visibility,
                    "published_at": published_at.isoformat(),
                },
                status="pending",
                publish_attempts=0,
            )
        )

    db.commit()
    return PostPublishResult(
        post_id=post.id,
        status="published",
        published_at=published_at,
        version_id=version.id,
        newsletter_status="queued" if event_exists is None else "already_processed",
    )

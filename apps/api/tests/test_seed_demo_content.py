"""Demo content seed command tests."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Post, PostVersion, Publication, User
from app.scripts.seed_demo_content import DEMO_PUBLICATIONS, seed_demo_content

DEMO_HANDLES = [publication.handle for publication in DEMO_PUBLICATIONS]


def test_seed_demo_content_is_idempotent(db: Session) -> None:
    first = seed_demo_content(
        db,
        owner_sub="local:demo@example.com",
        owner_email="demo@example.com",
        owner_name="Demo Writer",
    )
    second = seed_demo_content(
        db,
        owner_sub="local:demo@example.com",
        owner_email="demo@example.com",
        owner_name="Demo Writer",
    )

    assert first.users_created == 1
    assert first.publications_created == 2
    assert first.posts_created == 4
    assert first.post_versions_created == 3
    assert second.users_created == 0
    assert second.users_reused == 1
    assert second.publications_created == 0
    assert second.posts_created == 0
    assert second.post_versions_created == 0

    owner = db.scalar(select(User).where(User.cognito_sub == "local:demo@example.com"))
    assert owner is not None
    assert (
        db.scalar(select(func.count()).select_from(Publication).where(Publication.handle.in_(DEMO_HANDLES)))
        == 2
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(Post)
            .join(Publication, Post.publication_id == Publication.id)
            .where(Publication.handle.in_(DEMO_HANDLES))
        )
        == 4
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(PostVersion)
            .join(Post, PostVersion.post_id == Post.id)
            .join(Publication, Post.publication_id == Publication.id)
            .where(Publication.handle.in_(DEMO_HANDLES))
        )
        == 3
    )


def test_seed_demo_content_creates_published_snapshots(db: Session) -> None:
    seed_demo_content(
        db,
        owner_sub="local:demo@example.com",
        owner_email="demo@example.com",
        owner_name="Demo Writer",
    )

    published_posts = db.scalars(
        select(Post)
        .join(Publication, Post.publication_id == Publication.id)
        .where(Post.status == "published", Publication.handle.in_(DEMO_HANDLES))
    ).all()
    versions = db.scalars(
        select(PostVersion)
        .join(Post, PostVersion.post_id == Post.id)
        .join(Publication, Post.publication_id == Publication.id)
        .where(Publication.handle.in_(DEMO_HANDLES))
    ).all()

    assert len(published_posts) == 3
    assert {version.post_id for version in versions} == {post.id for post in published_posts}

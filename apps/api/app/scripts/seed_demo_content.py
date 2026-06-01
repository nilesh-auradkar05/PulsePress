"""Seed original demo publications and posts.

The seed data is first-party PulsePress sample content. Do not replace it with
copied article bodies from Medium or any other third-party source unless the
project has explicit rights to republish that content.
"""

from __future__ import annotations

import argparse
import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import Post, PostVersion, Publication, User


@dataclass(frozen=True)
class DemoPost:
    title: str
    slug: str
    body: str
    status: str
    visibility: str


@dataclass(frozen=True)
class DemoPublication:
    handle: str
    name: str
    description: str
    posts: Sequence[DemoPost]


@dataclass(frozen=True)
class SeedResult:
    users_created: int = 0
    users_reused: int = 0
    publications_created: int = 0
    publications_reused: int = 0
    posts_created: int = 0
    posts_reused: int = 0
    post_versions_created: int = 0
    post_versions_reused: int = 0

    def lines(self) -> list[str]:
        return [
            f"users: created={self.users_created} reused={self.users_reused}",
            (
                "publications: "
                f"created={self.publications_created} reused={self.publications_reused}"
            ),
            f"posts: created={self.posts_created} reused={self.posts_reused}",
            (
                "post_versions: "
                f"created={self.post_versions_created} reused={self.post_versions_reused}"
            ),
        ]


DEMO_PUBLICATIONS: tuple[DemoPublication, ...] = (
    DemoPublication(
        handle="pulsepress-labs",
        name="PulsePress Labs",
        description="Practical notes on building reliable creator platforms.",
        posts=(
            DemoPost(
                title="Designing a Publishing Flow That Can Fail Safely",
                slug="designing-a-publishing-flow-that-can-fail-safely",
                status="published",
                visibility="free",
                body=(
                    "Reliable publishing systems treat the publish button as a boundary. "
                    "Draft edits can stay simple, but the moment a post becomes public the "
                    "system needs a durable snapshot, a clear event, and enough metadata for "
                    "downstream workers to recover without guessing. PulsePress keeps that "
                    "boundary small: one post state transition, one immutable version, and one "
                    "outbox event for fanout."
                ),
            ),
            DemoPost(
                title="Why Creator Dashboards Need Boring Data Models",
                slug="why-creator-dashboards-need-boring-data-models",
                status="draft",
                visibility="free",
                body=(
                    "A useful creator dashboard starts with plain facts: posts, subscribers, "
                    "gifts, and revenue. The first version should prefer understandable tables "
                    "over clever analytics. Once the source of truth is stable, charts and live "
                    "streams can layer on top without becoming the only place the numbers exist."
                ),
            ),
        ),
    ),
    DemoPublication(
        handle="signal-and-story",
        name="Signal and Story",
        description="Essays about writing, product judgment, and small software teams.",
        posts=(
            DemoPost(
                title="Writing Product Updates People Actually Read",
                slug="writing-product-updates-people-actually-read",
                status="published",
                visibility="free",
                body=(
                    "A product update earns attention when it respects the reader's time. "
                    "Start with what changed, explain who benefits, and save implementation "
                    "detail for the people who need it. The best updates feel specific, short, "
                    "and accountable."
                ),
            ),
            DemoPost(
                title="The Small Team Review Checklist",
                slug="the-small-team-review-checklist",
                status="published",
                visibility="paid",
                body=(
                    "Small teams need review habits that catch expensive mistakes without "
                    "slowing every decision. Check the contract, the migration path, the "
                    "observability signal, and the rollback story. If those four pieces are "
                    "clear, the implementation usually has enough shape to move."
                ),
            ),
        ),
    ),
)


def _get_or_create_user(
    db: Session,
    *,
    owner_sub: str,
    owner_email: str | None,
    owner_name: str,
) -> tuple[User, bool]:
    user = db.execute(select(User).where(User.cognito_sub == owner_sub)).scalar_one_or_none()
    if user is not None:
        return user, False

    user = User(cognito_sub=owner_sub, email=owner_email, display_name=owner_name)
    db.add(user)
    db.flush()
    return user, True


def _get_or_create_publication(
    db: Session,
    *,
    owner: User,
    demo: DemoPublication,
) -> tuple[Publication, bool]:
    publication = db.execute(
        select(Publication).where(Publication.handle == demo.handle)
    ).scalar_one_or_none()
    if publication is not None:
        if publication.owner_user_id != owner.id:
            raise ValueError(
                f"seed publication handle '{demo.handle}' already belongs to another user"
            )
        return publication, False

    publication = Publication(
        owner_user_id=owner.id,
        handle=demo.handle,
        name=demo.name,
        description=demo.description,
        is_active=True,
    )
    db.add(publication)
    db.flush()
    return publication, True


def _get_or_create_post(
    db: Session,
    *,
    owner: User,
    publication: Publication,
    demo: DemoPost,
    published_at: dt.datetime,
) -> tuple[Post, bool]:
    post = db.execute(
        select(Post).where(Post.publication_id == publication.id, Post.slug == demo.slug)
    ).scalar_one_or_none()
    if post is not None:
        return post, False

    post = Post(
        publication_id=publication.id,
        author_user_id=owner.id,
        title=demo.title,
        slug=demo.slug,
        body=demo.body,
        status=demo.status,
        visibility=demo.visibility,
        published_at=published_at if demo.status == "published" else None,
    )
    db.add(post)
    db.flush()
    return post, True


def _ensure_post_version(db: Session, *, post: Post) -> bool:
    existing = db.execute(
        select(PostVersion).where(PostVersion.post_id == post.id).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return False

    db.add(
        PostVersion(
            post_id=post.id,
            title=post.title,
            body=post.body,
            visibility=post.visibility,
        )
    )
    db.flush()
    return True


def seed_demo_content(
    db: Session,
    *,
    owner_sub: str,
    owner_email: str | None,
    owner_name: str,
) -> SeedResult:
    """Create or reuse the canonical demo user, publications, posts, and snapshots."""

    if not owner_sub.strip():
        raise ValueError("owner_sub is required")
    if not owner_name.strip():
        raise ValueError("owner_name is required")

    result = SeedResult()
    owner, user_created = _get_or_create_user(
        db,
        owner_sub=owner_sub.strip(),
        owner_email=owner_email.strip().lower() if owner_email else None,
        owner_name=owner_name.strip(),
    )
    result = SeedResult(
        users_created=1 if user_created else 0,
        users_reused=0 if user_created else 1,
    )

    published_at = dt.datetime.now(dt.UTC)

    for demo_publication in DEMO_PUBLICATIONS:
        publication, publication_created = _get_or_create_publication(
            db, owner=owner, demo=demo_publication
        )
        result = SeedResult(
            users_created=result.users_created,
            users_reused=result.users_reused,
            publications_created=result.publications_created + int(publication_created),
            publications_reused=result.publications_reused + int(not publication_created),
            posts_created=result.posts_created,
            posts_reused=result.posts_reused,
            post_versions_created=result.post_versions_created,
            post_versions_reused=result.post_versions_reused,
        )

        for demo_post in demo_publication.posts:
            post, post_created = _get_or_create_post(
                db,
                owner=owner,
                publication=publication,
                demo=demo_post,
                published_at=published_at,
            )
            version_created = False
            version_reused = False
            if post.status == "published":
                version_created = _ensure_post_version(db, post=post)
                version_reused = not version_created

            result = SeedResult(
                users_created=result.users_created,
                users_reused=result.users_reused,
                publications_created=result.publications_created,
                publications_reused=result.publications_reused,
                posts_created=result.posts_created + int(post_created),
                posts_reused=result.posts_reused + int(not post_created),
                post_versions_created=result.post_versions_created + int(version_created),
                post_versions_reused=result.post_versions_reused + int(version_reused),
            )

    db.commit()
    return result


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed original PulsePress demo content.")
    parser.add_argument(
        "--owner-sub",
        required=True,
        help="Cognito/local subject for the owner user.",
    )
    parser.add_argument("--owner-email", default=None, help="Owner email address.")
    parser.add_argument("--owner-name", required=True, help="Owner display name.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    with Session(get_engine()) as db:
        result = seed_demo_content(
            db,
            owner_sub=args.owner_sub,
            owner_email=args.owner_email,
            owner_name=args.owner_name,
        )

    for line in result.lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

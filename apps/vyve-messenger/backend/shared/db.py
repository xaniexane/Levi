"""Database engine / session wiring shared by the VYVE backend servers (P3.3).

- ``DATABASE_URL`` env var selects the database. Unset → local SQLite file
  ``./vyve.db`` (persistent dev default). ``sqlite:///:memory:`` → ephemeral
  in-memory SQLite (used by the pytest suite so it runs without Postgres).
- ``postgresql://...`` URLs use psycopg2 (pinned in requirements.txt).
- Synchronous SQLAlchemy throughout: the servers are sync-style with async
  endpoints, so each request gets its own session via the ``get_db()``
  FastAPI dependency (session-per-request). No async SQLAlchemy.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./vyve.db")


def _make_engine(url: str):
    if url == "sqlite://" or url.startswith("sqlite:///:memory:"):
        # In-memory SQLite: a single shared connection so every session in
        # the process (including TestClient request threads) sees the same DB.
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    if url.startswith("sqlite:"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # postgresql://... → SQLAlchemy's default psycopg2 driver.
    return create_engine(url)


DATABASE_URL = database_url()
engine = _make_engine(DATABASE_URL)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


def init_db() -> None:
    """Create tables from the models if they do not exist yet.

    Alembic migrations are the upgrade path for real deployments; this is the
    zero-config bootstrap for dev/test so the servers start without any
    manual migration step.
    """
    from .models import Base

    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Demo seeding (replaces the old DEMO_USERS dict) ───────────────

DEMO_SEED_USERS: list[dict] = [
    {
        "username": "chauncey",
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "password": "changeme",
        "role": "user",
        "tier": "creator",
        "scopes": [
            "openid",
            "profile",
            "read:v1",
            "write:v1",
            "marketplace:v1",
            "ai_context:v1",
        ],
        "email": "chauncey@example.com",
        "display_name": "Chauncey",
    },
    {
        "username": "cj",
        "user_id": "00000000-0000-0000-0000-000000000001",
        "password": "admin",
        "role": "admin",
        "tier": "enterprise",
        "scopes": ["openid", "profile", "admin:v1", "read:v1", "write:v1"],
        "email": "cj@vyve.local",
        "display_name": "CJ",
    },
]


def seed_demo_users(db: Session) -> None:
    """Insert the demo users when VYVE_DEMO_MODE=true, if absent.

    Idempotent: existing usernames are left untouched, so re-seeding never
    overwrites real accounts or resets passwords.
    """
    import bcrypt  # local import: only needed when seeding

    from .models import User

    for seed in DEMO_SEED_USERS:
        exists = db.query(User).filter(User.username == seed["username"]).first()
        if exists:
            continue
        db.add(
            User(
                user_id=seed["user_id"],
                username=seed["username"],
                password_hash=bcrypt.hashpw(
                    seed["password"].encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8"),
                role=seed["role"],
                tier=seed["tier"],
                scopes=list(seed["scopes"]),
                email=seed["email"],
                display_name=seed["display_name"],
            )
        )
    db.commit()

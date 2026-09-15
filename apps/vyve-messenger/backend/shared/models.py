"""SQLAlchemy 2.0 models for the VYVE backend (P3.3).

Reconciliation notes — where ``infrastructure/database/schema.sql`` and the
running server code disagree, the CODE's semantics win (the code is the
running contract); schema.sql's table names are kept where sensible:

1. Table names kept from schema.sql: ``users``, ``devices``, ``oauth_tokens``,
   ``conversations``, ``conversation_participants``, ``messages``.
2. New tables not present in schema.sql: ``auth_codes`` (the OAuth
   authorization-code store was dict-only in code) and ``message_queue``
   (the offline-delivery queue was a dict in the messaging server).
3. IDs are TEXT, not UUID: the running contract uses arbitrary string IDs —
   device IDs like ``"d1"`` (see tests), messaging user IDs like ``"alice"`` /
   ``"bob"``. ``users.user_id`` stores the UUIDs as strings.
4. ``users.password_hash`` added — schema.sql has no password column, but the
   OAuth demo login verifies bcrypt password hashes.
5. ``users`` drops the NOT NULL ``identity_signing_key`` /
   ``identity_encryption_key`` BYTEA columns (demo users have no keys) and the
   username CHECK constraints (code accepts ``"chauncey"`` / ``"cj"``).
6. ``oauth_tokens`` stores REFRESH tokens only — access tokens are stateless
   RS256 JWTs and are never persisted. Lookup key is ``token_hash`` (hex
   SHA-256 of the token), exactly as the code keyed its dict. The schema.sql
   ``access_token_hash`` / ``id_token_hash`` columns are dropped.
7. ``devices.signing_key`` / ``encryption_key`` are TEXT — the code stores
   base64-encoded key strings, not BYTEA.
8. ``messages.recipient_key_ids`` / ``attachment_ids`` are JSON — the code
   stores string lists, not UUID[].
9. Delivery/read receipts are JSON columns on ``messages`` (the code's
   ``delivery_receipts`` / ``read_receipts`` dicts are keyed by user ID), not
   the schema.sql ``message_recipients`` table (keyed by device).
10. ``conversation_participants`` carries the per-user ``unread_count`` the
    code kept in the conversation dict; ``created_by`` on ``conversations``
    preserves the code's rule that the creator is excluded from the
    ``unread_count`` map.
11. schema.sql tables the servers never touch (follows, blocks, communities,
    posts, marketplace, attachments, audit_log, security_events) are
    intentionally NOT modeled here; the alembic migration covers only what
    the servers actually use.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base


Base = declarative_base()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ── OAuth: users, auth codes, refresh tokens, devices ──────────────

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True)
    username = Column(String(32), unique=True, nullable=False, index=True)
    # Not in schema.sql — required by the code's bcrypt demo login.
    password_hash = Column(String(128), nullable=False)
    display_name = Column(String(64))
    email = Column(String(255))
    role = Column(String(20), nullable=False, default="user")
    tier = Column(String(20), nullable=False, default="free")
    scopes = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class AuthCode(Base):
    """OAuth authorization codes. No equivalent table in schema.sql."""

    __tablename__ = "auth_codes"

    code = Column(String(64), primary_key=True)
    client_id = Column(String(128), nullable=False)
    redirect_uri = Column(Text, nullable=False)
    user_id = Column(String(36), nullable=False, index=True)
    username = Column(String(32), nullable=False)
    scopes = Column(JSON, nullable=False, default=list)
    code_challenge = Column(String(128), nullable=False)
    code_challenge_method = Column(String(16), nullable=False, default="S256")
    issued_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, nullable=False, default=False)


class OAuthToken(Base):
    """Refresh tokens. Code semantics: refresh tokens only (access tokens are
    stateless RS256 JWTs). Table name kept from schema.sql."""

    __tablename__ = "oauth_tokens"

    token_id = Column(String(36), primary_key=True, default=_uuid)
    # Hex SHA-256 of the token — the lookup key the code used for its dict.
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(
        String(36), ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    scopes = Column(JSON, nullable=False, default=list)
    device_id = Column(String(128), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    rotated_from = Column(String(64), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class Device(Base):
    """Registered E2EE devices. PK is TEXT: the code registers arbitrary
    device IDs (e.g. "d1" in tests), not UUIDs."""

    __tablename__ = "devices"

    device_id = Column(String(128), primary_key=True)
    user_id = Column(
        String(36), ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    device_name = Column(String(64), nullable=False)
    device_type = Column(String(16), nullable=False)
    # TEXT, not BYTEA: the code stores base64-encoded key strings.
    signing_key = Column(Text, nullable=False)
    encryption_key = Column(Text, nullable=False)
    registered_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    trusted = Column(Boolean, nullable=False, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


# ── Messaging: conversations, messages, offline queue ─────────────

class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(String(36), primary_key=True, default=_uuid)
    conversation_type = Column(String(16), nullable=False)
    name = Column(String(128), nullable=True)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_activity = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    conversation_id = Column(
        String(36), ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Plain string, no FK: the messaging server accepts arbitrary user IDs
    # ("alice", "bob", ...) that may not exist in the OAuth users table.
    user_id = Column(String(36), primary_key=True, index=True)
    joined_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    left_at = Column(DateTime(timezone=True), nullable=True)
    unread_count = Column(Integer, nullable=False, default=0)


class Message(Base):
    """Encrypted message envelopes. Code semantics: user-deleted messages
    become tombstones (status='deleted', deleted_at set)."""

    __tablename__ = "messages"

    message_id = Column(String(36), primary_key=True, default=_uuid)
    conversation_id = Column(
        String(36), ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    sender_id = Column(String(36), nullable=False, index=True)
    sender_key_id = Column(String(16), nullable=False)
    # JSON string lists in the code, not UUID[].
    recipient_key_ids = Column(JSON, nullable=False, default=list)
    ephemeral_pubkey = Column(Text, nullable=False)
    nonce = Column(Text, nullable=False)
    ciphertext = Column(Text, nullable=False)
    signature = Column(Text, nullable=False)
    size_bucket = Column(String(8), nullable=False, default="small")
    attachment_ids = Column(JSON, nullable=False, default=list)
    reply_to = Column(String(36), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    status = Column(String(16), nullable=False, default="queued")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    # Keyed by user ID, per the code's delivery_receipts / read_receipts dicts.
    delivery_receipts = Column(JSON, nullable=False, default=dict)
    read_receipts = Column(JSON, nullable=False, default=dict)


class MessageQueue(Base):
    """Offline-delivery queue rows. No equivalent table in schema.sql."""

    __tablename__ = "message_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    message_id = Column(
        String(36), ForeignKey("messages.message_id", ondelete="CASCADE"),
        nullable=False,
    )
    queued_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

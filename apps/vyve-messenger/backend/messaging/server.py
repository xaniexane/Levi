#!/usr/bin/env python3
"""
VYVE Messaging Service
======================
Minimal production-ready messaging backend for VYVE Messenger.

Key design principle: SERVER NEVER SEES PLAINTEXT MESSAGE CONTENT.

All message content is end-to-end encrypted client-side using libsodium (PyNaCl).
This service handles:
  - Message queuing and delivery
  - Multi-device synchronization
  - Delivery receipts
  - Group/channel management
  - WebSocket for real-time delivery

Persistence (P3.3): conversations, messages and the offline-delivery queue are
stored in a database via SQLAlchemy (``shared/models.py`` + ``shared/db.py``),
replacing the old module-level dicts. ``DATABASE_URL`` selects the backend:
PostgreSQL via psycopg2 when set to a ``postgresql://`` URL, otherwise local
SQLite (``./vyve.db`` by default, in-memory for the pytest suite).
WebSocket connections stay in memory (transient by nature).

Usage:
    python server.py          # Development (localhost:8081)
    python server.py 9001    # Custom port
"""

from __future__ import annotations

import os
import sys
import json
import uuid
import time
import asyncio
import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional, Any

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Header,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import InvalidTokenError as JWTError

# The shared/ package lives next to oauth/ and messaging/ (i.e. backend/).
# Make it importable no matter which directory the server is launched from.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from shared.jwt_keys import JWT_ALGORITHM, get_public_key_pem
from shared.db import SessionLocal, get_db, init_db
from shared.models import (
    Conversation as ConversationModel,
    ConversationParticipant,
    Message,
    MessageQueue,
)


# ──────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────

# JWT verification uses the RSA public key shared with the OAuth provider
# (shared/jwt_keys.py). There is intentionally no JWT_SECRET fallback
# (fail-closed, P1.2).
OAUTH_ISSUER: str = os.getenv("OAUTH_ISSUER", "http://localhost:8080")
OAUTH_CLIENT_ID: str = os.getenv("OAUTH_CLIENT_ID", "vyve-messenger")

CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:8080,http://localhost:8081"
    ).split(",")
    if o.strip()
]

# ──────────────────────────────────────────────────────────────
# DATABASE BOOTSTRAP (P3.3)
# ──────────────────────────────────────────────────────────────

init_db()

# ──────────────────────────────────────────────────────────────
# TOKEN VALIDATION
# ──────────────────────────────────────────────────────────────


def validate_token(authorization: str = Header(...)) -> dict:
    """Validate bearer token and return claims."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    try:
        payload = jwt.decode(
            token,
            get_public_key_pem(),
            algorithms=[JWT_ALGORITHM],
            audience=OAUTH_CLIENT_ID,
            options={"require": ["exp", "sub"]},
        )
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ──────────────────────────────────────────────────────────────
# TRANSIENT STATE (WebSocket connections are not persisted)
# ──────────────────────────────────────────────────────────────

# WebSocket connections: user_id → list of WebSocket connections
active_connections: dict[str, list[WebSocket]] = {}

# ──────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────


class EncryptedMessageUpload(BaseModel):
    recipient_key_ids: list[str] = Field(..., description="Target device key IDs")
    ephemeral_pubkey: str = Field(
        ..., description="Base64-encoded ephemeral public key"
    )
    nonce: str = Field(..., description="Base64-encoded XChaCha20 nonce")
    ciphertext: str = Field(..., description="Base64-encoded ciphertext")
    signature: str = Field(..., description="Base64-encoded Ed25519 signature")
    size_bucket: str = Field(
        "small", description="Size: tiny, small, medium, large, xlarge"
    )
    attachment_ids: list[str] = Field(default_factory=list)
    reply_to: Optional[str] = None
    forward_policy: str = "allowed"


class EncryptedMessage(BaseModel):
    message_id: str
    conversation_id: str
    sender_key_id: str
    recipient_key_ids: list[str]
    ephemeral_pubkey: str
    nonce: str
    ciphertext: str
    signature: str
    size_bucket: str
    sent_at: str
    status: str = "queued"


class ConversationCreate(BaseModel):
    conversation_type: str = Field(..., pattern="^(direct|group|channel)$")
    participant_ids: list[str] = Field(..., min_length=1)
    name: Optional[str] = None


class Conversation(BaseModel):
    conversation_id: str
    conversation_type: str
    participants: list[str]
    name: Optional[str]
    created_at: str
    last_activity: str
    unread_count: dict[str, int] = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="VYVE Messaging Service",
    description="End-to-end encrypted messaging backend. Server never sees plaintext.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────


def get_size_bucket(ciphertext_b64: str) -> str:
    """Determine size bucket from base64-encoded ciphertext length."""
    # Approximate byte size from base64 (roughly 4 chars per 3 bytes)
    approx_bytes = (len(ciphertext_b64) * 3) // 4
    if approx_bytes < 500:
        return "tiny"
    elif approx_bytes < 5000:
        return "small"
    elif approx_bytes < 50000:
        return "medium"
    elif approx_bytes < 500000:
        return "large"
    else:
        return "xlarge"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    """Serialize a datetime as ISO-8601. SQLite returns naive datetimes;
    treat them as UTC to match the old ``datetime.now(timezone.utc)``
    output format."""
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _active_participants(
    db: Session, conversation_id: str
) -> list[ConversationParticipant]:
    return (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.left_at.is_(None),
        )
        .all()
    )


def _get_conversation_or_404(db: Session, conversation_id: str) -> ConversationModel:
    conv = (
        db.query(ConversationModel)
        .filter(ConversationModel.conversation_id == conversation_id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _require_participant(
    db: Session, conversation_id: str, user_id: str
) -> ConversationModel:
    conv = _get_conversation_or_404(db, conversation_id)
    is_participant = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
            ConversationParticipant.left_at.is_(None),
        )
        .first()
    )
    if not is_participant:
        raise HTTPException(status_code=403, detail="Not a participant")
    return conv


def _conversation_to_dict(db: Session, conv: ConversationModel) -> dict:
    participants = _active_participants(db, conv.conversation_id)
    return {
        "conversation_id": conv.conversation_id,
        "conversation_type": conv.conversation_type,
        # Preserves the old shape: unread_count excludes the creator, who was
        # added to participants but never got an unread_count entry.
        "participants": [p.user_id for p in participants],
        "name": conv.name,
        "created_at": _iso(conv.created_at),
        "last_activity": _iso(conv.last_activity),
        "unread_count": {
            p.user_id: p.unread_count
            for p in participants
            if p.user_id != conv.created_by
        },
    }


def _message_to_dict(m: Message) -> dict:
    if m.status == "deleted" and m.deleted_at is not None:
        # Tombstone — exact shape the old code returned after deletion.
        return {
            "message_id": m.message_id,
            "conversation_id": m.conversation_id,
            "status": "deleted",
            "deleted_at": _iso(m.deleted_at),
            "sender_id": m.sender_id,
        }
    d = {
        "message_id": m.message_id,
        "conversation_id": m.conversation_id,
        "sender_key_id": m.sender_key_id,
        "sender_id": m.sender_id,  # Server knows WHO sent, but not WHAT
        "recipient_key_ids": list(m.recipient_key_ids or []),
        "ephemeral_pubkey": m.ephemeral_pubkey,
        "nonce": m.nonce,
        "ciphertext": m.ciphertext,
        "signature": m.signature,
        "size_bucket": m.size_bucket,
        "sent_at": _iso(m.sent_at),
        "status": m.status,
        "attachment_ids": list(m.attachment_ids or []),
        "reply_to": m.reply_to,
    }
    if m.delivery_receipts:
        d["delivery_receipts"] = dict(m.delivery_receipts)
    if m.read_receipts:
        d["read_receipts"] = dict(m.read_receipts)
    return d


def _get_message_or_404(db: Session, message_id: str) -> Message:
    msg = db.query(Message).filter(Message.message_id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg


async def _deliver_to_recipients(db: Session, conversation_id: str, message: dict):
    """Push message to all connected recipient clients via WebSocket."""
    participants = _active_participants(db, conversation_id)
    if not participants:
        return

    for p in participants:
        user_id = p.user_id
        if user_id in active_connections:
            for ws in active_connections[user_id]:
                try:
                    await ws.send_json(
                        {
                            "type": "new_message",
                            "conversation_id": conversation_id,
                            "message": message,
                        }
                    )
                except Exception:
                    pass  # Connection may have died


# ──────────────────────────────────────────────────────────────
# CONVERSATIONS
# ──────────────────────────────────────────────────────────────


@app.get("/conversations")
def list_conversations(
    user: dict = Depends(validate_token), db: Session = Depends(get_db)
):
    """List all conversations for the authenticated user."""
    user_id = user["sub"]
    convs = (
        db.query(ConversationModel)
        .join(
            ConversationParticipant,
            ConversationModel.conversation_id
            == ConversationParticipant.conversation_id,
        )
        .filter(
            ConversationParticipant.user_id == user_id,
            ConversationParticipant.left_at.is_(None),
        )
        .all()
    )
    return {"conversations": [_conversation_to_dict(db, c) for c in convs]}


@app.post("/conversations", status_code=201)
async def create_conversation(
    body: ConversationCreate,
    user: dict = Depends(validate_token),
    db: Session = Depends(get_db),
):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    now = _utcnow()

    conv = ConversationModel(
        conversation_id=conversation_id,
        conversation_type=body.conversation_type,
        name=body.name,
        created_by=user["sub"],
        created_at=now,
        last_activity=now,
    )
    db.add(conv)
    participants = list(set(body.participant_ids + [user["sub"]]))
    for p in participants:
        db.add(
            ConversationParticipant(
                conversation_id=conversation_id,
                user_id=p,
                joined_at=now,
                unread_count=0,
            )
        )
    db.commit()

    conv_dict = _conversation_to_dict(db, conv)

    # Notify all participants
    for p in participants:
        if p in active_connections:
            for ws in active_connections[p]:
                try:
                    await ws.send_json(
                        {"type": "conversation_created", "conversation": conv_dict}
                    )
                except Exception:
                    pass

    return conv_dict


@app.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    user: dict = Depends(validate_token),
    db: Session = Depends(get_db),
):
    """Get a specific conversation."""
    conv = _require_participant(db, conversation_id, user["sub"])
    return _conversation_to_dict(db, conv)


@app.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    user: dict = Depends(validate_token),
    db: Session = Depends(get_db),
):
    """Delete a conversation (user-side)."""
    _require_participant(db, conversation_id, user["sub"])

    # Remove user from participants (don't delete if others remain).
    # Hard-delete the participant row, matching the old in-memory behavior
    # (the user was removed from the participants list entirely).
    db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user["sub"],
    ).delete()
    remaining = _active_participants(db, conversation_id)
    if not remaining:
        db.query(ConversationModel).filter(
            ConversationModel.conversation_id == conversation_id
        ).delete()
    db.commit()

    return None


# ──────────────────────────────────────────────────────────────
# MESSAGES
# ──────────────────────────────────────────────────────────────


@app.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = None,
    user: dict = Depends(validate_token),
    db: Session = Depends(get_db),
):
    """Get messages in a conversation.

    Returns encrypted messages only — server cannot read content.
    Messages are returned newest-first.
    """
    _require_participant(db, conversation_id, user["sub"])

    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.sent_at.desc())
        .all()
    )

    if before:
        # Same string-comparison semantics the old in-memory code used
        # (ISO-8601 timestamps sort lexicographically).
        msgs = [m for m in msgs if _iso(m.sent_at) < before]

    return {"messages": [_message_to_dict(m) for m in msgs[:limit]], "total": len(msgs)}


@app.post("/conversations/{conversation_id}/messages", status_code=201)
async def send_message(
    conversation_id: str,
    body: EncryptedMessageUpload,
    user: dict = Depends(validate_token),
    db: Session = Depends(get_db),
):
    """Send an encrypted message.

    The server receives only:
      - Ciphertext (unreadable without recipient's private key)
      - Sender/recipient key IDs
      - Ephemeral public key (for key agreement)
      - Nonce
      - Signature (for authenticity)
      - Size bucket (approximate)

    The server CANNOT read the message content.
    """
    conv = _require_participant(db, conversation_id, user["sub"])

    # Generate message ID and store
    message_id = str(uuid.uuid4())
    now = _utcnow()

    # Determine sender's key ID (from token or header — in production, from device registry)
    sender_key_id = hashlib.sha256(
        f"{user['sub']}-{body.recipient_key_ids[0] if body.recipient_key_ids else 'unknown'}".encode()
    ).hexdigest()[:8]

    msg = Message(
        message_id=message_id,
        conversation_id=conversation_id,
        sender_id=user["sub"],  # Server knows WHO sent, but not WHAT
        sender_key_id=sender_key_id,
        recipient_key_ids=list(body.recipient_key_ids),
        ephemeral_pubkey=body.ephemeral_pubkey,
        nonce=body.nonce,
        ciphertext=body.ciphertext,
        signature=body.signature,
        size_bucket=get_size_bucket(body.ciphertext),
        attachment_ids=list(body.attachment_ids),
        reply_to=body.reply_to,
        sent_at=now,
        status="queued",
    )
    db.add(msg)

    # Update conversation last activity
    conv.last_activity = now

    # Queue for offline recipients
    for p in _active_participants(db, conversation_id):
        if p.user_id != user["sub"]:
            db.add(
                MessageQueue(user_id=p.user_id, message_id=message_id, queued_at=now)
            )
    db.commit()

    message = _message_to_dict(msg)

    # Deliver to connected recipients via WebSocket
    await _deliver_to_recipients(db, conversation_id, message)

    return message


@app.get("/messages/{message_id}")
def get_message(
    message_id: str, user: dict = Depends(validate_token), db: Session = Depends(get_db)
):
    """Get a specific encrypted message."""
    msg = _get_message_or_404(db, message_id)

    # Check if user is participant in the conversation
    _require_participant(db, msg.conversation_id, user["sub"])

    return _message_to_dict(msg)


@app.delete("/messages/{message_id}", status_code=204)
def delete_message(
    message_id: str, user: dict = Depends(validate_token), db: Session = Depends(get_db)
):
    """Delete a message (user-side deletion)."""
    msg = _get_message_or_404(db, message_id)

    # Only sender can delete their own messages
    if msg.sender_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Can only delete your own messages")

    # Soft delete — replace with tombstone
    msg.status = "deleted"
    msg.deleted_at = _utcnow()
    db.commit()
    return None


@app.get("/messages/{message_id}/deliver")
def mark_delivered(
    message_id: str, user: dict = Depends(validate_token), db: Session = Depends(get_db)
):
    """Mark a message as delivered to this user (receipt)."""
    msg = _get_message_or_404(db, message_id)

    receipts = dict(msg.delivery_receipts or {})
    receipts[user["sub"]] = _iso(_utcnow())
    msg.delivery_receipts = receipts  # reassign: SQLAlchemy can't see in-place mutation
    msg.status = "delivered"
    db.commit()
    return {"status": "delivered", "delivered_at": _iso(_utcnow())}


# ──────────────────────────────────────────────────────────────
# MESSAGE QUEUE (for offline delivery)
# ──────────────────────────────────────────────────────────────


@app.get("/queue")
def get_queue(user: dict = Depends(validate_token), db: Session = Depends(get_db)):
    """Get queued messages for offline users."""
    user_id = user["sub"]
    rows = (
        db.query(MessageQueue)
        .filter(MessageQueue.user_id == user_id)
        .order_by(MessageQueue.id.asc())
        .all()
    )
    queue = []
    for row in rows:
        msg = db.query(Message).filter(Message.message_id == row.message_id).first()
        if msg:
            queue.append(_message_to_dict(msg))
    # Return and clear queue
    db.query(MessageQueue).filter(MessageQueue.user_id == user_id).delete()
    db.commit()
    return {"messages": queue, "count": len(queue)}


# ──────────────────────────────────────────────────────────────
# WEBSOCKET (real-time delivery)
# ──────────────────────────────────────────────────────────────


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket for real-time message delivery.

    Connect: wss://api.vyve.local/ws/{user_id}
    Auth:    send JWT in first message after connect
    """
    await websocket.accept()
    db = SessionLocal()

    # Authenticate
    try:
        auth_msg = await websocket.receive_json()
        if auth_msg.get("type") != "auth":
            await websocket.close(code=4001, reason="Authentication required")
            db.close()
            return

        token = auth_msg.get("token")
        if not token:
            await websocket.close(code=4001, reason="Token required")
            db.close()
            return

        # Validate token
        try:
            payload = jwt.decode(
                token,
                get_public_key_pem(),
                algorithms=[JWT_ALGORITHM],
                audience=OAUTH_CLIENT_ID,
                options={"require": ["exp", "sub"]},
            )
            token_user_id = payload["sub"]
            if token_user_id != user_id:
                await websocket.close(code=4003, reason="Token mismatch")
                db.close()
                return
        except JWTError:
            await websocket.close(code=4002, reason="Invalid token")
            db.close()
            return

    except WebSocketDisconnect:
        db.close()
        return

    # Register connection
    if user_id not in active_connections:
        active_connections[user_id] = []
    active_connections[user_id].append(websocket)

    try:
        # Send queued messages
        rows = (
            db.query(MessageQueue)
            .filter(MessageQueue.user_id == user_id)
            .order_by(MessageQueue.id.asc())
            .all()
        )
        queued = []
        for row in rows:
            msg = db.query(Message).filter(Message.message_id == row.message_id).first()
            if msg:
                queued.append(_message_to_dict(msg))
        if queued:
            await websocket.send_json({"type": "queued_messages", "messages": queued})
            db.query(MessageQueue).filter(MessageQueue.user_id == user_id).delete()
            db.commit()

        # Send connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "user_id": user_id,
                "server_time": _iso(_utcnow()),
            }
        )

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "typing":
                # Broadcast typing indicator to conversation participants
                conv_id = data.get("conversation_id")
                conv = (
                    db.query(ConversationModel)
                    .filter(ConversationModel.conversation_id == conv_id)
                    .first()
                    if conv_id
                    else None
                )
                if conv:
                    for p in _active_participants(db, conv_id):
                        if p.user_id in active_connections and p.user_id != user_id:
                            for ws in active_connections[p.user_id]:
                                try:
                                    await ws.send_json(
                                        {
                                            "type": "typing",
                                            "conversation_id": conv_id,
                                            "user_id": user_id,
                                        }
                                    )
                                except Exception:
                                    pass

            elif data.get("type") == "read_receipt":
                msg_id = data.get("message_id")
                msg = (
                    db.query(Message).filter(Message.message_id == msg_id).first()
                    if msg_id
                    else None
                )
                if msg:
                    receipts = dict(msg.read_receipts or {})
                    receipts[user_id] = _iso(_utcnow())
                    msg.read_receipts = receipts
                    db.commit()

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup
        if user_id in active_connections:
            try:
                active_connections[user_id].remove(websocket)
                if not active_connections[user_id]:
                    del active_connections[user_id]
            except ValueError:
                pass
        db.close()


# ──────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────


@app.get("/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "service": "vyve-messaging",
        "version": "1.0.0",
        "conversations": db.query(ConversationModel).count(),
        "messages": db.query(Message).count(),
        "queued_messages": db.query(MessageQueue).count(),
        "active_connections": sum(len(v) for v in active_connections.values()),
    }


# ──────────────────────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    print(f"[VYVE Messaging] Starting on port {port}")
    print(f"[VYVE Messaging] WebSocket: ws://localhost:{port}/ws/{{user_id}}")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)

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

from fastapi import FastAPI, HTTPException, Depends, Header, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from jose import jwt, JWTError


# ──────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────

JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-CHANGE-IN-PRODUCTION")
JWT_ALGORITHM: str = "HS256"
OAUTH_ISSUER: str = os.getenv("OAUTH_ISSUER", "http://localhost:8080")


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
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require_exp": True, "require_sub": True}
        )
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ──────────────────────────────────────────────────────────────
# DATA STORES (replace with Redis + PostgreSQL in production)
# ──────────────────────────────────────────────────────────────

# Conversations: conversation_id → Conversation
conversations: dict[str, dict] = {}

# Messages: message_id → EncryptedMessage
messages: dict[str, dict] = {}

# Message queue: user_id → list of queued messages
message_queues: dict[str, list[dict]] = {}

# WebSocket connections: user_id → list of WebSocket connections
active_connections: dict[str, list[WebSocket]] = {}

# ──────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────

class EncryptedMessageUpload(BaseModel):
    recipient_key_ids: list[str] = Field(..., description="Target device key IDs")
    ephemeral_pubkey: str = Field(..., description="Base64-encoded ephemeral public key")
    nonce: str = Field(..., description="Base64-encoded XChaCha20 nonce")
    ciphertext: str = Field(..., description="Base64-encoded ciphertext")
    signature: str = Field(..., description="Base64-encoded Ed25519 signature")
    size_bucket: str = Field("small", description="Size: tiny, small, medium, large, xlarge")
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
    allow_origins=["*"],
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


async def _deliver_to_recipients(conversation_id: str, message: dict):
    """Push message to all connected recipient clients via WebSocket."""
    conversation = conversations.get(conversation_id)
    if not conversation:
        return
    
    for user_id in conversation["participants"]:
        if user_id in active_connections:
            for ws in active_connections[user_id]:
                try:
                    await ws.send_json({
                        "type": "new_message",
                        "conversation_id": conversation_id,
                        "message": message,
                    })
                except Exception:
                    pass  # Connection may have died


# ──────────────────────────────────────────────────────────────
# CONVERSATIONS
# ──────────────────────────────────────────────────────────────

@app.get("/conversations")
def list_conversations(user: dict = Depends(validate_token)):
    """List all conversations for the authenticated user."""
    user_id = user["sub"]
    result = []
    for conv in conversations.values():
        if user_id in conv["participants"]:
            result.append(conv)
    return {"conversations": result}


@app.post("/conversations", status_code=201)
def create_conversation(
    body: ConversationCreate,
    user: dict = Depends(validate_token)
):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    conv = {
        "conversation_id": conversation_id,
        "conversation_type": body.conversation_type,
        "participants": list(set(body.participant_ids + [user["sub"]])),
        "name": body.name,
        "created_at": now,
        "last_activity": now,
        "unread_count": {p: 0 for p in body.participant_ids},
    }
    conversations[conversation_id] = conv
    
    # Notify all participants
    for p in conv["participants"]:
        if p in active_connections:
            for ws in active_connections[p]:
                try:
                    await ws.send_json({"type": "conversation_created", "conversation": conv})
                except Exception:
                    pass
    
    return conv


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user: dict = Depends(validate_token)):
    """Get a specific conversation."""
    conv = conversations.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user["sub"] not in conv["participants"]:
        raise HTTPException(status_code=403, detail="Not a participant")
    return conv


@app.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, user: dict = Depends(validate_token)):
    """Delete a conversation (user-side)."""
    conv = conversations.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user["sub"] not in conv["participants"]:
        raise HTTPException(status_code=403, detail="Not a participant")
    
    # Remove user from participants (don't delete if others remain)
    conv["participants"].remove(user["sub"])
    if not conv["participants"]:
        del conversations[conversation_id]
    
    return None


# ──────────────────────────────────────────────────────────────
# MESSAGES
# ──────────────────────────────────────────────────────────────

@app.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = None,
    user: dict = Depends(validate_token)
):
    """Get messages in a conversation.
    
    Returns encrypted messages only — server cannot read content.
    Messages are returned newest-first.
    """
    conv = conversations.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user["sub"] not in conv["participants"]:
        raise HTTPException(status_code=403, detail="Not a participant")
    
    msgs = [
        m for m in messages.values()
        if m["conversation_id"] == conversation_id
    ]
    msgs.sort(key=lambda m: m["sent_at"], reverse=True)
    
    if before:
        msgs = [m for m in msgs if m["sent_at"] < before]
    
    return {"messages": msgs[:limit], "total": len(msgs)}


@app.post("/conversations/{conversation_id}/messages", status_code=201)
async def send_message(
    conversation_id: str,
    body: EncryptedMessageUpload,
    user: dict = Depends(validate_token)
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
    conv = conversations.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user["sub"] not in conv["participants"]:
        raise HTTPException(status_code=403, detail="Not a participant")
    
    # Generate message ID and store
    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Determine sender's key ID (from token or header — in production, from device registry)
    sender_key_id = hashlib.sha256(
        f"{user['sub']}-{body.recipient_key_ids[0] if body.recipient_key_ids else 'unknown'}".encode()
    ).hexdigest()[:8]
    
    message = {
        "message_id": message_id,
        "conversation_id": conversation_id,
        "sender_key_id": sender_key_id,
        "sender_id": user["sub"],  # Server knows WHO sent, but not WHAT
        "recipient_key_ids": body.recipient_key_ids,
        "ephemeral_pubkey": body.ephemeral_pubkey,
        "nonce": body.nonce,
        "ciphertext": body.ciphertext,
        "signature": body.signature,
        "size_bucket": get_size_bucket(body.ciphertext),
        "sent_at": now,
        "status": "queued",
        "attachment_ids": body.attachment_ids,
        "reply_to": body.reply_to,
    }
    
    messages[message_id] = message
    
    # Update conversation last activity
    conv["last_activity"] = now
    
    # Deliver to connected recipients via WebSocket
    await _deliver_to_recipients(conversation_id, message)
    
    # Queue for offline recipients
    for p in conv["participants"]:
        if p != user["sub"]:
            if p not in message_queues:
                message_queues[p] = []
            message_queues[p].append(message)
    
    return message


@app.get("/messages/{message_id}")
def get_message(message_id: str, user: dict = Depends(validate_token)):
    """Get a specific encrypted message."""
    msg = messages.get(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Check if user is participant in the conversation
    conv = conversations.get(msg["conversation_id"])
    if not conv or user["sub"] not in conv["participants"]:
        raise HTTPException(status_code=403, detail="Not a participant")
    
    return msg


@app.delete("/messages/{message_id}", status_code=204)
def delete_message(message_id: str, user: dict = Depends(validate_token)):
    """Delete a message (user-side deletion)."""
    msg = messages.get(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Only sender can delete their own messages
    if msg["sender_id"] != user["sub"]:
        raise HTTPException(status_code=403, detail="Can only delete your own messages")
    
    # Soft delete — replace with tombstone
    messages[message_id] = {
        "message_id": message_id,
        "conversation_id": msg["conversation_id"],
        "status": "deleted",
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "sender_id": user["sub"],
    }
    return None


@app.get("/messages/{message_id}/deliver")
def mark_delivered(message_id: str, user: dict = Depends(validate_token)):
    """Mark a message as delivered to this user (receipt)."""
    msg = messages.get(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    msg.setdefault("delivery_receipts", {})[user["sub"]] = datetime.now(timezone.utc).isoformat()
    msg["status"] = "delivered"
    return {"status": "delivered", "delivered_at": datetime.now(timezone.utc).isoformat()}


# ──────────────────────────────────────────────────────────────
# MESSAGE QUEUE (for offline delivery)
# ──────────────────────────────────────────────────────────────

@app.get("/queue")
def get_queue(user: dict = Depends(validate_token)):
    """Get queued messages for offline users."""
    user_id = user["sub"]
    queue = message_queues.get(user_id, [])
    # Return and clear queue
    message_queues[user_id] = []
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
    
    # Authenticate
    try:
        auth_msg = await websocket.receive_json()
        if auth_msg.get("type") != "auth":
            await websocket.close(code=4001, reason="Authentication required")
            return
        
        token = auth_msg.get("token")
        if not token:
            await websocket.close(code=4001, reason="Token required")
            return
        
        # Validate token
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            token_user_id = payload["sub"]
            if token_user_id != user_id:
                await websocket.close(code=4003, reason="Token mismatch")
                return
        except JWTError:
            await websocket.close(code=4002, reason="Invalid token")
            return
    
    except WebSocketDisconnect:
        pass
    
    # Register connection
    if user_id not in active_connections:
        active_connections[user_id] = []
    active_connections[user_id].append(websocket)
    
    try:
        # Send queued messages
        queue = message_queues.get(user_id, [])
        if queue:
            await websocket.send_json({"type": "queued_messages", "messages": queue})
            message_queues[user_id] = []
        
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "server_time": datetime.now(timezone.utc).isoformat(),
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "typing":
                # Broadcast typing indicator to conversation participants
                conv_id = data.get("conversation_id")
                if conv_id and conv_id in conversations:
                    conv = conversations[conv_id]
                    for p in conv["participants"]:
                        if p in active_connections and p != user_id:
                            for ws in active_connections[p]:
                                try:
                                    await ws.send_json({
                                        "type": "typing",
                                        "conversation_id": conv_id,
                                        "user_id": user_id,
                                    })
                                except Exception:
                                    pass
            
            elif data.get("type") == "read_receipt":
                msg_id = data.get("message_id")
                if msg_id and msg_id in messages:
                    messages[msg_id].setdefault("read_receipts", {})[user_id] = \
                        datetime.now(timezone.utc).isoformat()
            
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


# ──────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "vyve-messaging",
        "version": "1.0.0",
        "conversations": len(conversations),
        "messages": len(messages),
        "queued_messages": sum(len(q) for q in message_queues.values()),
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

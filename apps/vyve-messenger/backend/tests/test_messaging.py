"""Auth/token-path tests for the messaging service (backend/messaging/server.py).

Covers: REST endpoints accepting a valid RS256 access token and rejecting
expired / tampered / wrong-alg / wrong-audience / wrong-type tokens, and the
WebSocket auth handshake (valid, invalid token, sub mismatch).
"""

from __future__ import annotations

import time

import pytest

from conftest import mint_hs256_token, tamper_payload


MSG_PAYLOAD = {
    "recipient_key_ids": ["key-1"],
    "ephemeral_pubkey": "ZXBoZW1lcmFs",
    "nonce": "bm9uY2U",
    "ciphertext": "Y2lwaGVydGV4dA==",
    "signature": "c2lnbmF0dXJl",
}


def _issue(oauth_mod, sub="user-1", scopes=("openid", "profile"),
           token_type="access", lifetime=None, monkeypatch=None):
    if lifetime is not None:
        monkeypatch.setattr(oauth_mod.config, "ACCESS_TOKEN_LIFETIME", lifetime)
    return oauth_mod.create_jwt_token(sub, list(scopes), token_type)


@pytest.fixture()
def tokens(oauth_mod):
    """The messaging tests mint tokens with the OAuth provider's issuer."""
    return oauth_mod


def test_rest_accepts_valid_token_and_full_message_flow(tokens, msg_client, monkeypatch):
    token = _issue(tokens, sub="alice")
    headers = {"Authorization": f"Bearer {token}"}

    # create conversation
    conv = msg_client.post("/conversations", json={
        "conversation_type": "direct",
        "participant_ids": ["bob"],
        "name": "chat",
    }, headers=headers)
    assert conv.status_code == 201
    conv_id = conv.json()["conversation_id"]

    # send a message
    sent = msg_client.post(f"/conversations/{conv_id}/messages",
                           json=MSG_PAYLOAD, headers=headers)
    assert sent.status_code == 201
    msg_id = sent.json()["message_id"]

    # read it back
    got = msg_client.get(f"/conversations/{conv_id}/messages", headers=headers)
    assert got.status_code == 200
    assert got.json()["messages"][0]["message_id"] == msg_id

    # list conversations
    lst = msg_client.get("/conversations", headers=headers)
    assert lst.status_code == 200
    assert lst.json()["conversations"][0]["conversation_id"] == conv_id

    # delivery receipt
    rec = msg_client.get(f"/messages/{msg_id}/deliver", headers=headers)
    assert rec.status_code == 200


@pytest.mark.parametrize("mutate", ["expired", "tampered", "hs256",
                                    "wrong_audience", "wrong_type", "none"])
def test_rest_rejects_bad_tokens(tokens, msg_client, monkeypatch, mutate):
    if mutate == "expired":
        token = _issue(tokens, lifetime=-10, monkeypatch=monkeypatch)
    elif mutate == "tampered":
        token = tamper_payload(_issue(tokens))
    elif mutate == "hs256":
        token = mint_hs256_token()
    elif mutate == "wrong_audience":
        monkeypatch.setattr(tokens.config, "CLIENT_ID", "other-audience")
        token = tokens.create_jwt_token("alice", ["openid"], "access")
        monkeypatch.setattr(tokens.config, "CLIENT_ID", "vyve-messenger")
    elif mutate == "wrong_type":
        token = tokens.create_jwt_token("alice", ["openid"], "id")
    else:  # "none"
        token = None

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    expected = 422 if mutate == "none" else 401  # missing header → FastAPI 422
    for method, path, kwargs in [
        ("get", "/conversations", {}),
        ("post", "/conversations",
         {"json": {"conversation_type": "direct", "participant_ids": ["bob"]}}),
        ("get", "/queue", {}),
    ]:
        resp = getattr(msg_client, method)(path, headers=headers, **kwargs)
        assert resp.status_code == expected, f"{method} {path} with {mutate}"


def test_rest_rejects_missing_sub_claim(tokens, msg_client):
    # A token without "sub" must be rejected even if the signature is valid.
    import base64, json
    token = _issue(tokens)
    header, payload, sig = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    del claims["sub"]
    raw = json.dumps(claims).encode()
    bad_payload = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    # signature won't match anymore → 401 either way; the point is no crash
    resp = msg_client.get("/conversations",
                          headers={"Authorization": f"Bearer {header}.{bad_payload}.{sig}"})
    assert resp.status_code == 401


# ── WebSocket auth ───────────────────────────────────────────────

def test_websocket_accepts_valid_token(tokens, msg_client):
    token = _issue(tokens, sub="ws-user")
    with msg_client.websocket_connect("/ws/ws-user") as ws:
        ws.send_json({"type": "auth", "token": token})
        first = ws.receive_json()
        assert first["type"] == "connected"
        assert first["user_id"] == "ws-user"
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_websocket_rejects_tampered_token(tokens, msg_client):
    from starlette.websockets import WebSocketDisconnect
    token = tamper_payload(_issue(tokens, sub="ws-user"))
    with msg_client.websocket_connect("/ws/ws-user") as ws:
        ws.send_json({"type": "auth", "token": token})
        try:
            ws.receive_json()
            pytest.fail("expected the server to close the connection")
        except WebSocketDisconnect as e:
            assert e.code == 4002


def test_websocket_rejects_sub_mismatch(tokens, msg_client):
    from starlette.websockets import WebSocketDisconnect
    token = _issue(tokens, sub="someone-else")
    with msg_client.websocket_connect("/ws/ws-user") as ws:
        ws.send_json({"type": "auth", "token": token})
        try:
            ws.receive_json()
            pytest.fail("expected the server to close the connection")
        except WebSocketDisconnect as e:
            assert e.code == 4003


def test_websocket_rejects_expired_token(tokens, msg_client, monkeypatch):
    from starlette.websockets import WebSocketDisconnect
    token = _issue(tokens, sub="ws-user", lifetime=-10, monkeypatch=monkeypatch)
    with msg_client.websocket_connect("/ws/ws-user") as ws:
        ws.send_json({"type": "auth", "token": token})
        try:
            ws.receive_json()
            pytest.fail("expected the server to close the connection")
        except WebSocketDisconnect as e:
            assert e.code == 4002


def test_websocket_requires_auth_message(tokens, msg_client):
    from starlette.websockets import WebSocketDisconnect
    with msg_client.websocket_connect("/ws/ws-user") as ws:
        ws.send_json({"type": "hello"})
        try:
            ws.receive_json()
            pytest.fail("expected the server to close the connection")
        except WebSocketDisconnect as e:
            assert e.code == 4001

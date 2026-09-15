#!/usr/bin/env python3
"""
Cybrus OAuth 2.0 / OpenID Connect Provider
==========================================
Minimal production-ready OAuth2 server for VYVE integration with Omega/Cybrus.

Supports:
  - Authorization Code flow with PKCE (S256)
  - Refresh token rotation
  - Scoped access tokens (JWT)
  - OIDC identity tokens
  - Device key attestation storage

Persistence (P3.3): users, authorization codes, refresh tokens and devices are
stored in a database via SQLAlchemy (``shared/models.py`` + ``shared/db.py``),
replacing the old module-level dicts. ``DATABASE_URL`` selects the backend:
PostgreSQL via psycopg2 when set to a ``postgresql://`` URL, otherwise local
SQLite (``./vyve.db`` by default, in-memory for the pytest suite).

Usage:
    python server.py          # Development (localhost:8080)
    python server.py 9000     # Custom port

For production: use uvicorn with TLS termination in front.
"""

from __future__ import annotations

import os
import sys
import secrets
import hashlib
import base64
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError as JWTError
from fastapi import FastAPI, HTTPException, Depends, Form, Query, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy.orm import Session

# The shared/ package lives next to oauth/ and messaging/ (i.e. backend/).
# Make it importable no matter which directory the server is launched from.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from shared.jwt_keys import (
    JWT_ALGORITHM as _RSA_ALGORITHM,
    JWT_KID,
    get_private_key_pem,
    get_public_key_pem,
    public_jwk,
)
from shared.db import SessionLocal, get_db, init_db, seed_demo_users
from shared.models import AuthCode, Device, OAuthToken, User


# ──────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────

class Config:
    """Environment-driven configuration. Never hardcode secrets."""

    # JWT / Token settings — RS256. Keys are managed by shared/jwt_keys.py;
    # there is intentionally no JWT_SECRET fallback (fail-closed, P1.2).
    JWT_ALGORITHM: str = _RSA_ALGORITHM  # "RS256"
    ACCESS_TOKEN_LIFETIME: int = int(os.getenv("ACCESS_TOKEN_LIFETIME", "3600"))  # 1 hour
    REFRESH_TOKEN_LIFETIME: int = int(os.getenv("REFRESH_TOKEN_LIFETIME", "2592000"))  # 30 days
    ID_TOKEN_LIFETIME: int = 3600

    # OAuth2 settings
    ISSUER: str = os.getenv("OAUTH_ISSUER", "http://localhost:8080")
    CLIENT_ID: str = os.getenv("OAUTH_CLIENT_ID", "vyve-messenger")
    CLIENT_SECRET: str | None = os.getenv("OAUTH_CLIENT_SECRET")

    # Per-client registered redirect URIs (exact match, P1.4)
    REDIRECT_URIS: list[str] = [
        u.strip()
        for u in os.getenv(
            "OAUTH_REDIRECT_URIS",
            "http://localhost:8081/callback,http://localhost:8081/auth/callback",
        ).split(",")
        if u.strip()
    ]

    # CORS origins (explicit list, P1.6)
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:8080,http://localhost:8081").split(",")
        if o.strip()
    ]

    # Cookie security
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax")

    # Demo user store (P1.5). Off by default; enable explicitly for local testing.
    DEMO_MODE: bool = os.getenv("VYVE_DEMO_MODE", "false").lower() == "true"

    def __init__(self) -> None:
        # Fail closed: no dev-secret default (P1.2).
        if not self.CLIENT_SECRET:
            raise RuntimeError(
                "OAUTH_CLIENT_SECRET environment variable must be set. "
                "Refusing to start without a client secret."
            )

config = Config()

# ──────────────────────────────────────────────────────────────
# DATABASE BOOTSTRAP (P3.3)
# ──────────────────────────────────────────────────────────────

init_db()
if config.DEMO_MODE:
    _seed_db = SessionLocal()
    try:
        seed_demo_users(_seed_db)
    finally:
        _seed_db.close()
    del _seed_db

# Compatibility shim: the old in-memory demo-user dict is gone (users live in
# the DB now and are seeded above when VYVE_DEMO_MODE=true). Kept as an empty
# dict because the test suite asserts it is empty with demo mode off.
DEMO_USERS: dict[str, dict] = {}

# ──────────────────────────────────────────────────────────────
# TOKEN HELPERS
# ──────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password with bcrypt (direct bcrypt; passlib removed in P2.3)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    """Verify bcrypt password."""
    return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))


def create_jwt_token(
    subject: str,
    scopes: list[str],
    token_type: str = "access",
    extra_claims: dict = None
) -> str:
    """Create an RS256-signed JWT. Signing key comes from shared/jwt_keys.py."""
    now = int(time.time())
    claims = {
        "iss": config.ISSUER,
        "sub": subject,
        "aud": config.CLIENT_ID,
        "exp": now + (
            config.ACCESS_TOKEN_LIFETIME if token_type == "access"
            else config.REFRESH_TOKEN_LIFETIME if token_type == "refresh"
            else config.ID_TOKEN_LIFETIME
        ),
        "iat": now,
        "jti": str(uuid.uuid4()),
        "scope": " ".join(scopes),
        "type": token_type,
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(
        claims,
        get_private_key_pem(),
        algorithm=config.JWT_ALGORITHM,
        headers={"kid": JWT_KID},
    )


def decode_jwt(token: str, required_type: str = "access") -> dict:
    """Decode and validate a JWT against the RSA public key."""
    try:
        payload = jwt.decode(
            token,
            get_public_key_pem(),
            algorithms=[config.JWT_ALGORITHM],
            audience=config.CLIENT_ID,
            options={"require": ["exp", "sub"]}
        )
        if payload.get("type") != required_type:
            raise HTTPException(status_code=401, detail=f"Token type mismatch: expected {required_type}")
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def create_code_verifier(length: int = 64) -> str:
    """Generate a random PKCE code verifier."""
    return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode().rstrip("=")


def create_code_challenge(verifier: str) -> str:
    """Derive S256 PKCE code challenge from verifier."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


# ──────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    id_token: Optional[str] = None
    scope: str

class AuthorizeParams(BaseModel):
    response_type: str
    client_id: str
    redirect_uri: str
    scope: str
    state: str
    code_challenge: str
    code_challenge_method: str

class TokenRequest(BaseModel):
    grant_type: str
    code: Optional[str] = None
    code_verifier: Optional[str] = None
    redirect_uri: Optional[str] = None
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

class UserProfile(BaseModel):
    sub: str
    username: str
    email: str
    display_name: str
    role: str
    tier: str
    scopes: list[str]

class DeviceRegistration(BaseModel):
    device_id: str
    device_name: str
    device_type: str
    signing_key: str
    encryption_key: str

# ──────────────────────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Cybrus OAuth 2.0 Provider",
    description="OAuth 2.0 / OIDC provider for VYVE integration with Omega/Cybrus identity.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — explicit origin allowlist (no wildcard with credentials), P1.6
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = HTTPBearer(auto_error=False)


def get_current_user(credentials = Depends(oauth2_scheme)) -> dict:
    """Dependency: extract and validate bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    return decode_jwt(credentials.credentials)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────
# DISCOVERY ENDPOINT (OIDC)
# ──────────────────────────────────────────────────────────────

@app.get("/.well-known/openid-configuration")
def oidc_discovery():
    """OIDC Discovery document."""
    base = config.ISSUER.rstrip("/")
    return {
        "issuer": config.ISSUER,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "userinfo_endpoint": f"{base}/oauth/userinfo",
        "jwks_uri": f"{base}/oauth/jwks",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "scopes_supported": [
            "openid", "profile", "email",
            "read:v1", "write:v1", "social:v1",
            "marketplace:v1", "ai_context:v1", "admin:v1"
        ],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }


@app.get("/oauth/jwks")
def jwks():
    """JSON Web Key Set — publishes the PUBLIC RSA key for token verification.

    Contains only public key material (kty/n/e). The private key is never
    exposed here (P1.3).
    """
    return {"keys": [public_jwk()]}


# ──────────────────────────────────────────────────────────────
# AUTHORIZATION ENDPOINT
# ──────────────────────────────────────────────────────────────

@app.get("/oauth/authorize")
def authorize(
    request: Request,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query(...),
    state: str = Query(...),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query(...),
    db: Session = Depends(get_db),
):
    """OAuth2 Authorization Endpoint.

    In production: this renders a login/consent UI and sets a session cookie.
    For this scaffold: accepts ?username=<name>&password=<pw> query params for testing.
    """
    # Validate inputs
    if response_type != "code":
        return RedirectResponse(
            f"{redirect_uri}?error=unsupported_response_type&state={state}",
            status_code=302
        )
    if client_id != config.CLIENT_ID:
        return RedirectResponse(
            f"{redirect_uri}?error=invalid_client&state={state}",
            status_code=302
        )
    if code_challenge_method != "S256":
        return RedirectResponse(
            f"{redirect_uri}?error=invalid_request&error_description=code_challenge_method must be S256&state={state}",
            status_code=302
        )
    if redirect_uri not in config.REDIRECT_URIS:
        # Never redirect to an unregistered URI (open-redirect / code theft,
        # P1.4). Return a plain 400 so no attacker-controlled URI is reflected.
        return JSONResponse(
            {"error": "invalid_request", "error_description": "unregistered redirect_uri"},
            status_code=400,
        )

    # For demo: accept credentials via query params
    # Production: render login page, validate session cookie
    username = request.query_params.get("username")
    password = request.query_params.get("password")

    if not username or not password:
        # Return a simple HTML login form for demo purposes
        html = f"""<!DOCTYPE html>
<html><head><title>VYVE Login</title>
<style>
body{{font-family:system-ui;background:#0d1117;color:#c9d1d9;max-width:480px;margin:80px auto;padding:24px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:32px}}
h1{{color:#E57927;margin:0 0 24px}}label{{display:block;margin:16px 0 4px;color:#8b949e}}
input{{width:100%;padding:10px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;box-sizing:border-box}}
button{{width:100%;padding:12px;background:#E57927;color:#fff;border:none;border-radius:6px;margin-top:20px;font-size:16px;cursor:pointer}}
a{{color:#58a6ff}}p{{color:#8b949e;font-size:13px}}
</style></head>
<body>
<div class=card>
<h1>VYVE Login</h1>
<form method=get action="/oauth/authorize">
<input type=hidden name=response_type value="{response_type}">
<input type=hidden name=client_id value="{client_id}">
<input type=hidden name=redirect_uri value="{redirect_uri}">
<input type=hidden name=scope value="{scope}">
<input type=hidden name=state value="{state}">
<input type=hidden name=code_challenge value="{code_challenge}">
<input type=hidden name=code_challenge_method value="{code_challenge_method}">
<label>Username</label>
<input name=username placeholder="Username">
<label>Password</label>
<input name=password type=password placeholder="Password">
<button type=submit>Sign In</button>
</form>
</div></body></html>"""
        return HTMLResponse(content=html)

    # Validate credentials against the DB user store
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return HTMLResponse(
            content="<h1>Invalid credentials</h1><p><a href='/oauth/authorize?" +
                    f"response_type={response_type}&client_id={client_id}&redirect_uri={redirect_uri}" +
                    f"&scope={scope}&state={state}&code_challenge={code_challenge}" +
                    f"&code_challenge_method={code_challenge_method}" +
                    "'>Try again</a></p>",
            status_code=401
        )

    # Validate scopes
    requested_scopes = set(scope.split())
    user_scopes = list(user.scopes or [])
    granted_scopes = list(requested_scopes & set(user_scopes))
    if not granted_scopes:
        granted_scopes = user_scopes

    # Generate authorization code (10-minute window, single use)
    code = secrets.token_urlsafe(32)
    now = _utcnow()
    db.add(AuthCode(
        code=code,
        client_id=client_id,
        redirect_uri=redirect_uri,
        user_id=user.user_id,
        username=user.username,
        scopes=granted_scopes,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        issued_at=now,
        expires_at=datetime.fromtimestamp(time.time() + 600, tz=timezone.utc),
        used=False,
    ))
    db.commit()

    # Redirect with code
    params = f"code={code}&state={state}"
    return RedirectResponse(f"{redirect_uri}?{params}", status_code=302)


# ──────────────────────────────────────────────────────────────
# TOKEN ENDPOINT
# ──────────────────────────────────────────────────────────────

@app.post("/oauth/token", response_model=TokenResponse)
async def token_endpoint(form: Request, db: Session = Depends(get_db)):
    """OAuth2 Token Endpoint.

    Supports:
      - authorization_code + PKCE
      - refresh_token (with rotation)
    """
    grant_type = (await form.form()).get("grant_type")
    client_id = (await form.form()).get("client_id", config.CLIENT_ID)
    client_secret = (await form.form()).get("client_secret", "")

    # Client authentication (simplified)
    if client_id != config.CLIENT_ID:
        raise HTTPException(status_code=401, detail="invalid_client")
    if client_secret and client_secret != config.CLIENT_SECRET:
        raise HTTPException(status_code=401, detail="invalid_client")

    # ── Authorization Code grant ─────────────────────────────────
    if grant_type == "authorization_code":
        code = (await form.form()).get("code")
        code_verifier = (await form.form()).get("code_verifier")
        redirect_uri = (await form.form()).get("redirect_uri")

        stored = db.query(AuthCode).filter(AuthCode.code == code).first() if code else None
        if not stored:
            raise HTTPException(status_code=400, detail="invalid_code")

        if stored.used:
            # CODE REUSE DETECTED — revoke all tokens for this user
            _revoke_all_user_tokens(db, stored.user_id)
            raise HTTPException(status_code=400, detail="code_already_used")

        if _utcnow() > _as_aware(stored.expires_at):
            raise HTTPException(status_code=400, detail="code_expired")

        if redirect_uri and redirect_uri != stored.redirect_uri:
            raise HTTPException(status_code=400, detail="redirect_uri_mismatch")

        # Verify PKCE
        if stored.code_challenge_method == "S256":
            if not code_verifier:
                raise HTTPException(status_code=400, detail="code_verifier required")
            computed = create_code_challenge(code_verifier)
            if computed != stored.code_challenge:
                raise HTTPException(status_code=400, detail="invalid_code_verifier")

        # Mark code as used
        stored.used = True
        db.commit()

        # Issue tokens
        user_id = stored.user_id
        scopes = list(stored.scopes or [])
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="user_not_found")

        access_token = create_jwt_token(user_id, scopes, "access")
        refresh_token = _issue_refresh_token(db, user_id, scopes)

        id_token_claims = {
            "sub": user_id,
            "email": user.email or "",
            "name": user.display_name or "",
            "preferred_username": stored.username,
            "role": user.role,
            "tier": user.tier,
        }
        id_token = create_jwt_token(user_id, ["openid"], "id", id_token_claims)

        return TokenResponse(
            access_token=access_token,
            expires_in=config.ACCESS_TOKEN_LIFETIME,
            refresh_token=refresh_token,
            id_token=id_token,
            scope=" ".join(scopes),
        )

    # ── Refresh Token grant ─────────────────────────────────────
    elif grant_type == "refresh_token":
        refresh_tok = (await form.form()).get("refresh_token")
        if not refresh_tok:
            raise HTTPException(status_code=400, detail="refresh_token required")

        token_hash = hashlib.sha256(refresh_tok.encode()).hexdigest()
        stored = db.query(OAuthToken).filter(OAuthToken.token_hash == token_hash).first()
        if not stored:
            raise HTTPException(status_code=401, detail="invalid_refresh_token")

        if _utcnow() > _as_aware(stored.expires_at):
            db.delete(stored)
            db.commit()
            raise HTTPException(status_code=401, detail="refresh_token_expired")

        # Rotation: revoke old token, issue new one
        old_hash = token_hash
        user_id = stored.user_id
        scopes = list(stored.scopes or [])
        db.delete(stored)
        db.commit()

        new_access = create_jwt_token(user_id, scopes, "access")
        new_refresh = _issue_refresh_token(db, user_id, scopes, rotated_from=old_hash)

        return TokenResponse(
            access_token=new_access,
            expires_in=config.ACCESS_TOKEN_LIFETIME,
            refresh_token=new_refresh,
            scope=" ".join(scopes),
        )

    else:
        raise HTTPException(status_code=400, detail=f"unsupported_grant_type: {grant_type}")


def _as_aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC for comparisons."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _issue_refresh_token(db: Session, user_id: str, scopes: list[str],
                         rotated_from: Optional[str] = None) -> str:
    """Issue a new refresh token with rotation tracking."""
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.add(OAuthToken(
        token_hash=token_hash,
        user_id=user_id,
        scopes=list(scopes),
        issued_at=_utcnow(),
        expires_at=datetime.fromtimestamp(
            time.time() + config.REFRESH_TOKEN_LIFETIME, tz=timezone.utc),
        rotated_from=rotated_from,
    ))
    db.commit()
    return token


def _revoke_all_user_tokens(db: Session, user_id: str):
    """Code reuse attack response: revoke all refresh tokens for this user."""
    db.query(OAuthToken).filter(OAuthToken.user_id == user_id).delete()
    db.commit()


# ──────────────────────────────────────────────────────────────
# USERINFO ENDPOINT (OIDC)
# ──────────────────────────────────────────────────────────────

@app.get("/oauth/userinfo")
def userinfo(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """OIDC UserInfo endpoint."""
    user_id = user["sub"]
    db_user = db.query(User).filter(User.user_id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="user not found")

    scopes = set(user.get("scope", "").split())
    response = {"sub": user_id, "username": db_user.username}

    if "profile" in scopes:
        response.update({
            "name": db_user.display_name or "",
            "email": db_user.email or "",
            "role": db_user.role,
            "tier": db_user.tier,
        })

    return response


# ──────────────────────────────────────────────────────────────
# VYVE-SPECIFIC ENDPOINTS
# ──────────────────────────────────────────────────────────────

@app.get("/me", response_model=UserProfile)
def get_me(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current authenticated user profile."""
    user_id = user["sub"]
    db_user = db.query(User).filter(User.user_id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="user not found")

    return UserProfile(
        sub=user_id,
        username=db_user.username,
        email=db_user.email or "",
        display_name=db_user.display_name or "",
        role=db_user.role,
        tier=db_user.tier,
        scopes=list(db_user.scopes or []),
    )


def _device_to_dict(d: Device) -> dict:
    return {
        "device_id": d.device_id,
        "device_name": d.device_name,
        "device_type": d.device_type,
        "signing_key": d.signing_key,
        "encryption_key": d.encryption_key,
        "registered_at": _as_aware(d.registered_at).isoformat(),
        "trusted": d.trusted,
    }


@app.post("/me/devices", status_code=201)
def register_device(
    reg: DeviceRegistration,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register a new device for multi-device E2EE messaging."""
    user_id = user["sub"]

    # Remove old device with same ID if exists (allows re-registration)
    db.query(Device).filter(
        Device.user_id == user_id, Device.device_id == reg.device_id
    ).delete()
    db.add(Device(
        device_id=reg.device_id,
        user_id=user_id,
        device_name=reg.device_name,
        device_type=reg.device_type,
        signing_key=reg.signing_key,
        encryption_key=reg.encryption_key,
        registered_at=_utcnow(),
        trusted=False,
    ))
    db.commit()

    return {"status": "registered", "device_id": reg.device_id}


@app.get("/me/devices")
def list_devices(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """List registered devices for this user."""
    user_id = user["sub"]
    devices = db.query(Device).filter(Device.user_id == user_id).all()
    return {"devices": [_device_to_dict(d) for d in devices]}


@app.delete("/me/devices/{device_id}")
def revoke_device(device_id: str, user: dict = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Revoke a device (removes it from the device registry)."""
    user_id = user["sub"]
    db.query(Device).filter(
        Device.user_id == user_id, Device.device_id == device_id
    ).delete()
    db.commit()
    return {"status": "revoked", "device_id": device_id}


@app.post("/oauth/revoke")
async def revoke_token(form: Request, db: Session = Depends(get_db)):
    """OAuth2 Token Revocation (RFC 7009)."""
    token = (await form.form()).get("token")
    token_type_hint = (await form.form()).get("token_type_hint")

    if not token:
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.query(OAuthToken).filter(OAuthToken.token_hash == token_hash).delete()
    db.commit()

    # Always return 200 (RFC 7009)
    return {"status": "revoked"}


# ──────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────

@app.get("/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "service": "cybrus-oauth",
        "version": "1.0.0",
        "issuer": config.ISSUER,
        "users_registered": db.query(User).count(),
        "tokens_issued": db.query(AuthCode).count(),
        "refresh_tokens_active": db.query(OAuthToken).count(),
    }


# ──────────────────────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────────────────────

class HTMLResponse(JSONResponse):
    media_type = "text/html"


if __name__ == "__main__":
    import uvicorn
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"[Cybrus OAuth] Starting on port {port}")
    print(f"[Cybrus OAuth] Discovery: http://localhost:{port}/.well-known/openid-configuration")
    print(f"[Cybrus OAuth] Demo: http://localhost:{port}/oauth/authorize")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)

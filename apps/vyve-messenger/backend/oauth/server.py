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
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import FastAPI, HTTPException, Depends, Form, Query, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from itsdangerous import URLSafeTimedSerializer


# ──────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────

class Config:
    """Environment-driven configuration. Never hardcode secrets."""
    
    # JWT / Token settings
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-CHANGE-IN-PRODUCTION")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_LIFETIME: int = int(os.getenv("ACCESS_TOKEN_LIFETIME", "3600"))  # 1 hour
    REFRESH_TOKEN_LIFETIME: int = int(os.getenv("REFRESH_TOKEN_LIFETIME", "2592000"))  # 30 days
    ID_TOKEN_LIFETIME: int = 3600
    
    # OAuth2 settings
    ISSUER: str = os.getenv("OAUTH_ISSUER", "http://localhost:8080")
    CLIENT_ID: str = os.getenv("OAUTH_CLIENT_ID", "vyve-messenger")
    CLIENT_SECRET: str = os.getenv("OAUTH_CLIENT_SECRET", "dev-client-secret-CHANGE")
    
    # Cookie security
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax")
    
    # Demo user store (replace with Omega/Cybrus identity API in production)
    DEMO_MODE: bool = True

config = Config()

# ──────────────────────────────────────────────────────────────
# TOKEN HELPERS
# ──────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(raw: str, hashed: str) -> bool:
    """Verify bcrypt password."""
    return pwd_context.verify(raw, hashed)


def create_jwt_token(
    subject: str,
    scopes: list[str],
    token_type: str = "access",
    extra_claims: dict = None
) -> str:
    """Create a signed JWT."""
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
    return jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_jwt(token: str, required_type: str = "access") -> dict:
    """Decode and validate a JWT."""
    try:
        payload = jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
            audience=config.CLIENT_ID,
            options={"require_exp": True, "require_sub": True}
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
# IN-MEMORY STORES (replace with Redis + database in production)
# ──────────────────────────────────────────────────────────────

# Demo user store — maps username → {password_hash, user_id, role, scopes}
DEMO_USERS: dict[str, dict] = {
    "chauncey": {
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "password_hash": hash_password("changeme"),
        "role": "user",
        "tier": "creator",
        "scopes": ["openid", "profile", "read:v1", "write:v1", "marketplace:v1", "ai_context:v1"],
        "email": "chauncey@example.com",
        "display_name": "Chauncey",
    },
    "cj": {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "password_hash": hash_password("admin"),
        "role": "admin",
        "tier": "enterprise",
        "scopes": ["openid", "profile", "admin:v1", "read:v1", "write:v1"],
        "email": "cj@vyve.local",
        "display_name": "CJ",
    }
}

# Authorization codes: code → {code, client_id, redirect_uri, user_id, scopes, code_challenge, expires_at, used}
auth_codes: dict[str, dict] = {}

# Refresh tokens: token_hash → {user_id, scopes, device_id, expires_at, rotated_from}
refresh_tokens: dict[str, dict] = {}

# Devices: user_id → [{device_id, signing_key, encryption_key, registered_at}]
user_devices: dict[str, list[dict]] = {}

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

# CORS — restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
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
        "id_token_signing_alg_values_supported": ["HS256"],
    }


@app.get("/oauth/jwks")
def jwks():
    """JSON Web Key Set — exposes public key for token verification."""
    # In production: rotate keys, use RS256 or EdDSA with proper key management
    return {
        "keys": [{
            "kty": "oct",
            "alg": "HS256",
            "use": "sig",
            # This exposes the public component — the secret itself is the private key
            # In production use asymmetric keys (RS256/ES256) so the JWKS is safe to share
            "k": base64.urlsafe_b64encode(config.JWT_SECRET.encode()).decode().rstrip("="),
            "kid": "vyve-1",
        }]
    }


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
    if not redirect_uri.startswith("http"):
        return RedirectResponse(
            f"{redirect_uri}?error=invalid_request&error_description=invalid redirect_uri&state={state}",
            status_code=302
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
<input name=username placeholder="chauncey or cj">
<label>Password</label>
<input name=password type=password placeholder="changeme or admin">
<button type=submit>Sign In</button>
</form>
<p style=margin-top:16px>Demo: chauncey/changeme or cj/admin</p>
</div></body></html>"""
        return HTMLResponse(content=html)

    # Validate credentials
    user = DEMO_USERS.get(username)
    if not user or not verify_password(password, user["password_hash"]):
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
    granted_scopes = list(requested_scopes & set(user["scopes"]))
    if not granted_scopes:
        granted_scopes = user["scopes"]

    # Generate authorization code
    code = secrets.token_urlsafe(32)
    auth_codes[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "user_id": user["user_id"],
        "username": username,
        "scopes": granted_scopes,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "issued_at": time.time(),
        "expires_at": time.time() + 600,  # 10-minute window
        "used": False,
    }

    # Redirect with code
    params = f"code={code}&state={state}"
    return RedirectResponse(f"{redirect_uri}?{params}", status_code=302)


# ──────────────────────────────────────────────────────────────
# TOKEN ENDPOINT
# ──────────────────────────────────────────────────────────────

@app.post("/oauth/token", response_model=TokenResponse)
def token_endpoint(form: Request):
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

        if not code or code not in auth_codes:
            raise HTTPException(status_code=400, detail="invalid_code")
        
        stored = auth_codes[code]
        
        if stored["used"]:
            # CODE REUSE DETECTED — revoke all tokens for this user
            _revoke_all_user_tokens(stored["user_id"])
            raise HTTPException(status_code=400, detail="code_already_used")

        if time.time() > stored["expires_at"]:
            raise HTTPException(status_code=400, detail="code_expired")
        
        if redirect_uri and redirect_uri != stored["redirect_uri"]:
            raise HTTPException(status_code=400, detail="redirect_uri_mismatch")

        # Verify PKCE
        if stored["code_challenge_method"] == "S256":
            if not code_verifier:
                raise HTTPException(status_code=400, detail="code_verifier required")
            computed = create_code_challenge(code_verifier)
            if computed != stored["code_challenge"]:
                raise HTTPException(status_code=400, detail="invalid_code_verifier")

        # Mark code as used
        stored["used"] = True

        # Issue tokens
        user_id = stored["user_id"]
        scopes = stored["scopes"]
        user = next((u for u in DEMO_USERS.values() if u["user_id"] == user_id), None)
        if not user:
            raise HTTPException(status_code=400, detail="user_not_found")

        access_token = create_jwt_token(user_id, scopes, "access")
        refresh_token = _issue_refresh_token(user_id, scopes)
        
        id_token_claims = {
            "sub": user_id,
            "email": user.get("email", ""),
            "name": user.get("display_name", ""),
            "preferred_username": stored["username"],
            "role": user["role"],
            "tier": user["tier"],
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
        if token_hash not in refresh_tokens:
            raise HTTPException(status_code=401, detail="invalid_refresh_token")
        
        stored = refresh_tokens[token_hash]
        if time.time() > stored["expires_at"]:
            del refresh_tokens[token_hash]
            raise HTTPException(status_code=401, detail="refresh_token_expired")

        # Rotation: revoke old token, issue new one
        old_hash = token_hash
        stored["rotated_from"] = old_hash
        del refresh_tokens[old_hash]

        new_access = create_jwt_token(stored["user_id"], stored["scopes"], "access")
        new_refresh = _issue_refresh_token(stored["user_id"], stored["scopes"])

        return TokenResponse(
            access_token=new_access,
            expires_in=config.ACCESS_TOKEN_LIFETIME,
            refresh_token=new_refresh,
            scope=" ".join(stored["scopes"]),
        )

    else:
        raise HTTPException(status_code=400, detail=f"unsupported_grant_type: {grant_type}")


def _issue_refresh_token(user_id: str, scopes: list[str]) -> str:
    """Issue a new refresh token with rotation tracking."""
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    refresh_tokens[token_hash] = {
        "user_id": user_id,
        "scopes": scopes,
        "issued_at": time.time(),
        "expires_at": time.time() + config.REFRESH_TOKEN_LIFETIME,
        "rotated_from": None,
    }
    return token


def _revoke_all_user_tokens(user_id: str):
    """Code reuse attack response: revoke all refresh tokens for this user."""
    to_delete = [h for h, t in refresh_tokens.items() if t["user_id"] == user_id]
    for h in to_delete:
        del refresh_tokens[h]


# ──────────────────────────────────────────────────────────────
# USERINFO ENDPOINT (OIDC)
# ──────────────────────────────────────────────────────────────

@app.get("/oauth/userinfo")
def userinfo(user: dict = Depends(get_current_user)):
    """OIDC UserInfo endpoint."""
    user_id = user["sub"]
    db_user = next((u for u in DEMO_USERS.values() if u["user_id"] == user_id), None)
    if not db_user:
        raise HTTPException(status_code=404, detail="user not found")
    
    scopes = set(user.get("scope", "").split())
    response = {"sub": user_id, "username": db_user["username"]}
    
    if "profile" in scopes:
        response.update({
            "name": db_user.get("display_name", ""),
            "email": db_user.get("email", ""),
            "role": db_user["role"],
            "tier": db_user["tier"],
        })
    
    return response


# ──────────────────────────────────────────────────────────────
# VYVE-SPECIFIC ENDPOINTS
# ──────────────────────────────────────────────────────────────

@app.get("/me", response_model=UserProfile)
def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user profile."""
    user_id = user["sub"]
    db_user = next((u for u in DEMO_USERS.values() if u["user_id"] == user_id), None)
    if not db_user:
        raise HTTPException(status_code=404, detail="user not found")
    
    return UserProfile(
        sub=user_id,
        username=next((k for k, v in DEMO_USERS.items() if v["user_id"] == user_id), ""),
        email=db_user.get("email", ""),
        display_name=db_user.get("display_name", ""),
        role=db_user["role"],
        tier=db_user["tier"],
        scopes=db_user["scopes"],
    )


@app.post("/me/devices", status_code=201)
def register_device(
    reg: DeviceRegistration,
    user: dict = Depends(get_current_user)
):
    """Register a new device for multi-device E2EE messaging."""
    user_id = user["sub"]
    if user_id not in user_devices:
        user_devices[user_id] = []
    
    device = {
        "device_id": reg.device_id,
        "device_name": reg.device_name,
        "device_type": reg.device_type,
        "signing_key": reg.signing_key,
        "encryption_key": reg.encryption_key,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "trusted": False,
    }
    
    # Remove old device with same ID if exists (allows re-registration)
    user_devices[user_id] = [d for d in user_devices[user_id] if d["device_id"] != reg.device_id]
    user_devices[user_id].append(device)
    
    return {"status": "registered", "device_id": reg.device_id}


@app.get("/me/devices")
def list_devices(user: dict = Depends(get_current_user)):
    """List registered devices for this user."""
    user_id = user["sub"]
    return {"devices": user_devices.get(user_id, [])}


@app.delete("/me/devices/{device_id}")
def revoke_device(device_id: str, user: dict = Depends(get_current_user)):
    """Revoke a device (removes it from user_devices)."""
    user_id = user["sub"]
    if user_id in user_devices:
        user_devices[user_id] = [d for d in user_devices[user_id] if d["device_id"] != device_id]
    return {"status": "revoked", "device_id": device_id}


@app.post("/oauth/revoke")
def revoke_token(form: Request):
    """OAuth2 Token Revocation (RFC 7009)."""
    token = (await form.form()).get("token")
    token_type_hint = (await form.form()).get("token_type_hint")
    
    if not token:
        return JSONResponse({"error": "invalid_request"}, status_code=400)
    
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if token_hash in refresh_tokens:
        del refresh_tokens[token_hash]
    
    # Always return 200 (RFC 7009)
    return {"status": "revoked"}


# ──────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "cybrus-oauth",
        "version": "1.0.0",
        "issuer": config.ISSUER,
        "users_registered": len(DEMO_USERS),
        "tokens_issued": len(auth_codes),
        "refresh_tokens_active": len(refresh_tokens),
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
    print(f"[Cybrus OAuth]   Test user: chauncey / changeme")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)

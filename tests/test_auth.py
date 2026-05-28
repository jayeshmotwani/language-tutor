"""
Auth endpoint tests — covers all /auth/* routes.

Uses the `client` fixture (in-memory SQLite, no bot mock).
"""

from datetime import datetime, timedelta, timezone

from jose import jwt


# ── POST /auth/register ───────────────────────────────────────────────────────

async def test_register_success(client):
    resp = await client.post(
        "/auth/register",
        json={"name": "Alice", "email": "alice@example.com", "password": "securepass1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["name"] == "Alice"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "hashed_password" not in data


async def test_register_duplicate_email(client):
    payload = {"name": "Bob", "email": "bob@example.com", "password": "securepass1"}
    r1 = await client.post("/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/auth/register", json=payload)
    assert r2.status_code == 400
    assert "already registered" in r2.json()["detail"]


# ── POST /auth/login ──────────────────────────────────────────────────────────

async def test_login_success(client, registered_user):
    resp = await client.post("/auth/login", json=registered_user)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client, registered_user):
    resp = await client.post(
        "/auth/login",
        json={"email": registered_user["email"], "password": "wrongpassword"},
    )
    assert resp.status_code == 401


async def test_login_nonexistent_email(client):
    resp = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "somepassword"},
    )
    assert resp.status_code == 401


# ── GET /auth/me ──────────────────────────────────────────────────────────────

async def test_me_with_valid_token(client, auth_headers):
    resp = await client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"


async def test_me_without_token(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_with_malformed_token(client):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert resp.status_code == 401


async def test_me_with_expired_token(client, registered_user):
    from app.auth.service import JWT_ALGORITHM, JWT_SECRET_KEY

    expired = jwt.encode(
        {
            "sub": "999",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


# ── POST /auth/refresh ────────────────────────────────────────────────────────

async def test_refresh_success(client, registered_user):
    login_resp = await client.post("/auth/login", json=registered_user)
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # Verify the new access token is actually valid by hitting a protected endpoint.
    me_resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == registered_user["email"]


async def test_refresh_with_invalid_token(client):
    resp = await client.post("/auth/refresh", json={"refresh_token": "invalid.token.value"})
    assert resp.status_code == 401


async def test_refresh_with_access_token_rejected(client, registered_user):
    """Passing an access token to /refresh must be rejected (wrong type claim)."""
    login_resp = await client.post("/auth/login", json=registered_user)
    access_token = login_resp.json()["access_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401

"""
Tests for the original /health, /start-session, and /chat endpoints.

Uses the `bot_client` fixture (DB override + mocked bot) so no real OpenAI
calls are made.  /health uses the plain `client` because it needs no bot.
"""


# ── GET /health ───────────────────────────────────────────────────────────────

async def test_health_no_auth_required(client):
    """/health is public — any caller can reach it without a token."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "bot_name" in data


# ── POST /start-session ───────────────────────────────────────────────────────

async def test_start_session_without_token(bot_client):
    resp = await bot_client.post(
        "/start-session",
        json={"session_id": "sess-001", "target_language": "French"},
    )
    assert resp.status_code == 401


async def test_start_session_with_valid_token(bot_client, bot_auth_headers):
    resp = await bot_client.post(
        "/start-session",
        json={"session_id": "sess-001", "target_language": "French"},
        headers=bot_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sess-001"
    assert data["language"] == "French"
    assert "message" in data
    assert len(data["message"]) > 0


# ── POST /chat ────────────────────────────────────────────────────────────────

async def test_chat_without_token(bot_client):
    resp = await bot_client.post(
        "/chat",
        json={"session_id": "sess-001", "message": "Bonjour"},
    )
    assert resp.status_code == 401


async def test_chat_with_valid_token(bot_client, bot_auth_headers):
    # Start the session first, then send a message.
    await bot_client.post(
        "/start-session",
        json={"session_id": "sess-chat", "target_language": "French"},
        headers=bot_auth_headers,
    )
    resp = await bot_client.post(
        "/chat",
        json={"session_id": "sess-chat", "message": "Comment allez-vous?"},
        headers=bot_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sess-chat"
    assert data["language"] == "French"
    assert "response" in data
    assert len(data["response"]) > 0

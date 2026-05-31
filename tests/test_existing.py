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


async def test_chat_rate_limit_enforced(bot_client, bot_auth_headers):
    """After DAILY_MESSAGE_LIMIT messages, /chat returns 429."""
    for i in range(3):
        resp = await bot_client.post(
            "/start-session",
            json={"session_id": f"sess-rl-{i}", "target_language": "French"},
            headers=bot_auth_headers,
        )
    for i in range(3):
        resp = await bot_client.post(
            "/chat",
            json={"session_id": f"sess-rl-{i}", "message": f"message {i}"},
            headers=bot_auth_headers,
        )
        assert resp.status_code == 200

    # 4th message must be rejected
    resp = await bot_client.post(
        "/chat",
        json={"session_id": "sess-rl-0", "message": "one too many"},
        headers=bot_auth_headers,
    )
    assert resp.status_code == 429
    data = resp.json()
    assert data["detail"]["error"] == "rate_limit_exceeded"


async def test_me_includes_rate_limit_fields(client, auth_headers):
    """GET /auth/me must return daily_message_count, daily_message_limit, messages_remaining."""
    resp = await client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "daily_message_count" in data
    assert "daily_message_limit" in data
    assert "messages_remaining" in data
    assert data["messages_remaining"] == data["daily_message_limit"] - data["daily_message_count"]


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

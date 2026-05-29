"""
Tests for /sessions endpoints and the chat persistence side-effects
on /start-session and /chat.

Uses bot_client + bot_auth_headers from conftest (DB override + mocked bot).
"""

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from unittest.mock import MagicMock, patch

from app.database import Base, get_db
from main import app

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def chat_engine():
    engine = create_async_engine(
        _TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def chat_client(chat_engine):
    """HTTP client with DB override and mocked bot for chat session tests."""
    TestSession = async_sessionmaker(chat_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    fake_session = MagicMock()
    fake_session.target_language = "French"

    with patch("main.bot") as mock_bot:
        mock_bot.start_session.return_value = "Bonjour! I'm Lexie, your French tutor!"
        mock_bot.chat.return_value = "Très bien! That means 'Very good' in French."
        mock_bot.session_manager.get_session.return_value = fake_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def chat_auth_headers(chat_client):
    """Register + login via chat_client; return Authorization header dict."""
    await chat_client.post(
        "/auth/register",
        json={"name": "Chat User", "email": "chatuser@example.com", "password": "password123"},
    )
    resp = await chat_client.post(
        "/auth/login",
        json={"email": "chatuser@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _register_and_login(client, email: str) -> dict:
    await client.post(
        "/auth/register",
        json={"name": "Other", "email": email, "password": "password123"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── POST /sessions ────────────────────────────────────────────────────────────


async def test_create_session_returns_id_and_language(chat_client, chat_auth_headers):
    resp = await chat_client.post(
        "/sessions",
        json={"language": "Spanish"},
        headers=chat_auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["language"] == "Spanish"
    assert "id" in data
    assert data["title"] is None


async def test_create_session_requires_auth(chat_client):
    resp = await chat_client.post("/sessions", json={"language": "Spanish"})
    assert resp.status_code == 401


# ── GET /sessions ─────────────────────────────────────────────────────────────


async def test_list_sessions_newest_first(chat_client, chat_auth_headers):
    for lang in ["French", "Spanish", "German"]:
        await chat_client.post("/sessions", json={"language": lang}, headers=chat_auth_headers)

    resp = await chat_client.get("/sessions", headers=chat_auth_headers)
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 3
    # newest first — last created should appear first
    assert sessions[0]["language"] == "German"


async def test_list_sessions_cap_at_50(chat_client, chat_auth_headers):
    for i in range(55):
        await chat_client.post(
            "/sessions", json={"language": f"Lang{i}"}, headers=chat_auth_headers
        )
    resp = await chat_client.get("/sessions", headers=chat_auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 50


async def test_list_sessions_requires_auth(chat_client):
    resp = await chat_client.get("/sessions")
    assert resp.status_code == 401


# ── GET /sessions/{id} ────────────────────────────────────────────────────────


async def test_get_session_detail_includes_messages(chat_client, chat_auth_headers):
    sid = str(uuid.uuid4())

    await chat_client.post(
        "/start-session",
        json={"session_id": sid, "target_language": "French"},
        headers=chat_auth_headers,
    )
    await chat_client.post(
        "/chat",
        json={"session_id": sid, "message": "Bonjour"},
        headers=chat_auth_headers,
    )

    resp = await chat_client.get(f"/sessions/{sid}", headers=chat_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sid
    assert data["language"] == "French"
    # greeting (assistant) + user + assistant = 3 messages
    assert len(data["messages"]) == 3
    assert data["messages"][0]["role"] == "assistant"
    assert data["messages"][1]["role"] == "user"
    assert data["messages"][2]["role"] == "assistant"


async def test_get_session_detail_requires_auth(chat_client, chat_auth_headers):
    resp = await chat_client.post(
        "/sessions", json={"language": "French"}, headers=chat_auth_headers
    )
    sid = resp.json()["id"]
    resp = await chat_client.get(f"/sessions/{sid}")
    assert resp.status_code == 401


async def test_get_session_404_for_nonexistent(chat_client, chat_auth_headers):
    resp = await chat_client.get(f"/sessions/{uuid.uuid4()}", headers=chat_auth_headers)
    assert resp.status_code == 404


async def test_get_session_404_for_another_users_session(chat_client, chat_auth_headers):
    # Create a session as user A.
    resp = await chat_client.post(
        "/sessions", json={"language": "French"}, headers=chat_auth_headers
    )
    sid = resp.json()["id"]

    # Register and log in as user B.
    other_headers = await _register_and_login(chat_client, "other@example.com")

    # User B should get 404 when accessing user A's session.
    resp = await chat_client.get(f"/sessions/{sid}", headers=other_headers)
    assert resp.status_code == 404


# ── DELETE /sessions/{id} ─────────────────────────────────────────────────────


async def test_delete_session_returns_204(chat_client, chat_auth_headers):
    resp = await chat_client.post(
        "/sessions", json={"language": "French"}, headers=chat_auth_headers
    )
    sid = resp.json()["id"]

    resp = await chat_client.delete(f"/sessions/{sid}", headers=chat_auth_headers)
    assert resp.status_code == 204


async def test_delete_session_subsequent_get_returns_404(chat_client, chat_auth_headers):
    resp = await chat_client.post(
        "/sessions", json={"language": "French"}, headers=chat_auth_headers
    )
    sid = resp.json()["id"]

    await chat_client.delete(f"/sessions/{sid}", headers=chat_auth_headers)

    resp = await chat_client.get(f"/sessions/{sid}", headers=chat_auth_headers)
    assert resp.status_code == 404


async def test_delete_session_requires_auth(chat_client, chat_auth_headers):
    resp = await chat_client.post(
        "/sessions", json={"language": "French"}, headers=chat_auth_headers
    )
    sid = resp.json()["id"]
    resp = await chat_client.delete(f"/sessions/{sid}")
    assert resp.status_code == 401


# ── Title auto-generation ─────────────────────────────────────────────────────


async def test_title_set_on_first_user_message(chat_client, chat_auth_headers):
    sid = str(uuid.uuid4())

    await chat_client.post(
        "/start-session",
        json={"session_id": sid, "target_language": "French"},
        headers=chat_auth_headers,
    )
    await chat_client.post(
        "/chat",
        json={"session_id": sid, "message": "How do I say hello in French?"},
        headers=chat_auth_headers,
    )

    resp = await chat_client.get(f"/sessions/{sid}", headers=chat_auth_headers)
    assert resp.json()["title"] == "How do I say hello in French?"


async def test_title_trimmed_at_word_boundary(chat_client, chat_auth_headers):
    sid = str(uuid.uuid4())

    await chat_client.post(
        "/start-session",
        json={"session_id": sid, "target_language": "French"},
        headers=chat_auth_headers,
    )
    # 65-char message — should be trimmed to ≤60 chars at a word boundary
    long_msg = "Can you please teach me how to conjugate verbs in the present tense"
    await chat_client.post(
        "/chat",
        json={"session_id": sid, "message": long_msg},
        headers=chat_auth_headers,
    )

    resp = await chat_client.get(f"/sessions/{sid}", headers=chat_auth_headers)
    title = resp.json()["title"]
    assert len(title) <= 60
    assert not title.endswith(" ")
    # must not cut a word mid-way — the next char in the original (if any) must be a space
    if len(long_msg) > 60:
        assert long_msg[len(title)] == " "


async def test_title_not_overwritten_on_subsequent_messages(chat_client, chat_auth_headers):
    sid = str(uuid.uuid4())

    await chat_client.post(
        "/start-session",
        json={"session_id": sid, "target_language": "French"},
        headers=chat_auth_headers,
    )
    await chat_client.post(
        "/chat",
        json={"session_id": sid, "message": "First message"},
        headers=chat_auth_headers,
    )
    await chat_client.post(
        "/chat",
        json={"session_id": sid, "message": "Second message"},
        headers=chat_auth_headers,
    )

    resp = await chat_client.get(f"/sessions/{sid}", headers=chat_auth_headers)
    assert resp.json()["title"] == "First message"

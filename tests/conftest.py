"""
Shared pytest fixtures.

Environment variables MUST be set before any app module is imported because
main.py validates OPENAI_API_KEY at import time and app/database.py reads
DATABASE_URL at import time.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-not-real")
os.environ.setdefault("DAILY_MESSAGE_LIMIT", "3")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-do-not-use-in-prod!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from main import app  # noqa: E402

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    """Fresh in-memory SQLite database per test function."""
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
async def client(test_engine):
    """HTTP client with DB override. No bot mock — use for auth endpoint tests."""
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def bot_client(test_engine):
    """HTTP client with DB override AND a mocked bot — use for /start-session and /chat tests."""
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

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
async def registered_user(client):
    """Register a test user and return their credentials dict."""
    resp = await client.post(
        "/auth/register",
        json={"name": "Test User", "email": "test@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    return {"email": "test@example.com", "password": "password123"}


@pytest_asyncio.fixture
async def auth_headers(client, registered_user):
    """Login and return an Authorization header dict for the test user."""
    resp = await client.post("/auth/login", json=registered_user)
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def bot_auth_headers(bot_client):
    """Register + login via bot_client; return Authorization header dict."""
    await bot_client.post(
        "/auth/register",
        json={"name": "Bot User", "email": "botuser@example.com", "password": "password123"},
    )
    resp = await bot_client.post(
        "/auth/login",
        json={"email": "botuser@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

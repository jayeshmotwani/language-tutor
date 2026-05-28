# Language Tutor — Lexie

AI-powered language tutoring chatbot ("Lexie") backed by FastAPI, OpenAI GPT-4o-mini, and ChromaDB for semantic context retrieval. Users authenticate via JWT Bearer tokens before accessing tutoring sessions.

## Project Structure

```
language-tutor/
├── main.py              # FastAPI app entry point — routes, CORS, router includes
├── app/
│   ├── bot.py           # Core business logic — LanguageTutorBot class
│   ├── database.py      # Async SQLAlchemy engine, Base, get_db dependency
│   ├── embeddings.py    # ChromaDB wrapper — EmbeddingService class
│   ├── models.py        # Pydantic request/response schemas (DO NOT MODIFY)
│   ├── session.py       # In-memory session state — Session + SessionManager
│   └── auth/
│       ├── __init__.py
│       ├── dependencies.py  # get_current_user() — FastAPI Depends guard
│       ├── models.py        # SQLAlchemy User ORM model
│       ├── router.py        # /auth endpoints (register, login, refresh, me)
│       ├── schemas.py       # Pydantic auth schemas (separate from app/models.py)
│       └── service.py       # Password hashing, JWT creation/decoding, DB queries
├── alembic/
│   ├── env.py           # Async Alembic migration environment
│   ├── script.py.mako   # Revision file template
│   └── versions/        # Generated migration scripts go here
├── tests/
│   ├── conftest.py      # Shared fixtures — in-memory SQLite, client, bot mock
│   ├── test_auth.py     # 11 tests covering all /auth/* routes
│   └── test_existing.py # 5 tests for /health, /start-session, /chat with auth
├── docs/
│   └── ec2-deployment-guide.md
├── alembic.ini
├── pytest.ini
├── requirements.txt
└── .env.example
```

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **AI Model**: OpenAI `gpt-4o-mini`
- **Embeddings**: OpenAI `text-embedding-3-small`
- **Vector DB**: ChromaDB (persistent local, stored in `./chroma_data/`)
- **Auth**: JWT Bearer tokens via `python-jose`, passwords hashed with `passlib[bcrypt]`
- **Database**: MySQL via SQLAlchemy async (`aiomysql` driver) + Alembic migrations
- **Validation**: Pydantic v2
- **Testing**: pytest + pytest-asyncio + httpx (in-memory SQLite via `aiosqlite`)
- **Language**: Python 3.11+

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

cp .env.example .env           # Fill in all required values (see Environment Variables below)
```

## Running the App

```bash
uvicorn main:app --reload
# API docs: http://localhost:8000/docs
```

Or directly:
```bash
python main.py
```

The app validates `OPENAI_API_KEY` at startup and raises `RuntimeError` if missing.

## Database Setup

The app uses MySQL in production via async SQLAlchemy. You must have MySQL running and `DATABASE_URL` set in `.env` before running migrations.

```bash
# Generate the first migration (auto-detects models from app/auth/models.py)
alembic revision --autogenerate -m "create users table"

# Apply migrations to the database
alembic upgrade head

# Roll back one migration
alembic downgrade -1
```

Alembic reads `DATABASE_URL` from the environment — the `sqlalchemy.url` in `alembic.ini` is a placeholder only.

## Running the Test Suite

Tests use an in-memory SQLite database and a mocked bot — no real MySQL, OpenAI, or ChromaDB calls are made.

```bash
pytest tests/ -v
```

16 tests should all pass. To run a single file:
```bash
pytest tests/test_auth.py -v
pytest tests/test_existing.py -v
```

## API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/health` | None | Health check — returns `{status, bot_name}` |
| `POST` | `/auth/register` | None | Register a new user; returns user object |
| `POST` | `/auth/login` | None | Login; returns JWT access token + refresh token |
| `POST` | `/auth/refresh` | None | Exchange refresh token for a new access token |
| `GET` | `/auth/me` | Bearer | Return the currently authenticated user |
| `POST` | `/start-session` | Bearer | Initialize tutoring session, returns Lexie's greeting |
| `POST` | `/chat` | Bearer | Send a message, receive Lexie's tutoring response |

**Request shapes** are defined in `app/models.py` (tutoring) and `app/auth/schemas.py` (auth):
- `StartSessionRequest`: `session_id`, `target_language`, optional `user_name`
- `ChatRequest`: `session_id`, `message`
- `UserRegisterRequest`: `name`, `email`, `password` (min 8 chars)
- `UserLoginRequest`: `email`, `password`
- `RefreshTokenRequest`: `refresh_token`

## Key Architecture Decisions

**Semantic memory over full history**: Rather than passing the full conversation to GPT on every turn, each user/bot exchange is embedded and stored in ChromaDB. On each new message, the top-3 semantically relevant past exchanges are retrieved and injected into the system prompt. This keeps token cost low while preserving topical continuity.

**Session isolation**: ChromaDB queries filter by `session_id` metadata so sessions never bleed into each other.

**In-memory sessions**: `SessionManager` stores sessions in a plain dict. `MAX_HISTORY_MESSAGES = 20` caps the rolling conversation history passed to OpenAI to prevent token overflow. Sessions are lost on server restart — there is no persistent session store.

**JWT Bearer auth**: Access tokens are short-lived (default 30 min); refresh tokens are long-lived (default 7 days). Both carry a `type` claim (`"access"` / `"refresh"`) so tokens cannot be cross-used. `HTTPBearer(auto_error=False)` is used so missing tokens return `401` rather than FastAPI's default `403`.

**Async database layer**: All DB access goes through `async def get_db()` in `app/database.py`, which yields an `AsyncSession`. The dependency is overridden in tests with a test-scoped session backed by in-memory SQLite + `StaticPool`, so all connections within a test share the same in-memory database.

**Test isolation strategy**: Each test function gets a freshly created in-memory SQLite database (via the `test_engine` fixture). The bot is patched at `main.bot` in the `bot_client` fixture so `/start-session` and `/chat` tests never call OpenAI.

**CORS**: Configured to allow React frontends on `localhost:3000` and `localhost:5173`. Update `main.py` `allow_origins` for production.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT and embeddings |
| `DATABASE_URL` | Yes | Async DB URL — e.g. `mysql+aiomysql://root:pass@localhost:3306/language_tutor` |
| `JWT_SECRET_KEY` | Yes | Long random string used to sign JWTs. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | No | JWT signing algorithm. Default: `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Access token TTL in minutes. Default: `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Refresh token TTL in days. Default: `7` |

## Deployment

See [`docs/ec2-deployment-guide.md`](docs/ec2-deployment-guide.md) for AWS EC2 + systemd setup. The app runs on `0.0.0.0:8000` by default.

## Developer Gotchas

- **`app/models.py` is frozen** — all auth-related Pydantic schemas live in `app/auth/schemas.py`. Do not add auth models to `app/models.py`.
- **`app/auth/models.py` must be imported before any `Base.metadata.create_all` call** — it registers the `User` table on `Base`. This happens automatically at runtime because `main.py` imports from `app.auth.router`, which imports from `app.auth.models`. In Alembic's `env.py`, `import app.auth.models` is explicit for the same reason.
- **`conftest.py` sets env vars at module level, before any app imports** — if you add a new module that reads env vars at import time, set the test value in `conftest.py` before the relevant import line.
- **SQLite vs MySQL type differences** — tests use SQLite; production uses MySQL. SQLite ignores `String(n)` length limits and stores `DateTime` as text. Test data that would violate MySQL constraints (e.g. strings over 255 chars) would pass in tests but fail in production.
- **The bot makes blocking OpenAI calls inside async route handlers** — this blocks the event loop, which is acceptable for this POC. For production, wrap bot calls in `asyncio.to_thread()`.
- **ChromaDB creates `./chroma_data/` on first run** — this directory is gitignored. Delete it to reset the vector store.

# Language Tutor Chatbot — Lexie

A friendly, text-based language tutor chatbot built with **FastAPI**, **GPT-4o-mini**, and **ChromaDB**. Meet **Lexie** — short for *lexicon* — your patient, encouraging AI language tutor.

## Features

- Secure JWT-based authentication — register, log in, and access tutoring with a Bearer token
- Introduce yourself to Lexie and tell her which language you want to learn
- She remembers your conversation within a session and adapts to your level
- Past exchanges are stored as embeddings in ChromaDB and retrieved as context, so Lexie stays relevant across a long session
- Persistent chat session storage (MySQL) — sessions and messages survive server restarts
- Session history API with title auto-generation from the first user message
- Clean OOP design: `LanguageTutorBot`, `EmbeddingService`, `SessionManager`

## Project Structure

```
language-tutor/
├── main.py                  # FastAPI app — routes, CORS, router includes
├── app/
│   ├── __init__.py
│   ├── bot.py               # LanguageTutorBot — orchestrates chat logic
│   ├── database.py          # Async SQLAlchemy engine, Base, get_db dependency
│   ├── embeddings.py        # EmbeddingService — ChromaDB + OpenAI embeddings
│   ├── models.py            # Pydantic request/response schemas (tutoring only)
│   ├── session.py           # SessionManager — in-memory session state
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── dependencies.py  # get_current_user() FastAPI dependency
│   │   ├── models.py        # SQLAlchemy User ORM model
│   │   ├── router.py        # /auth endpoints
│   │   ├── schemas.py       # Pydantic auth request/response schemas
│   │   └── service.py       # Password hashing, JWT logic, DB queries
│   └── chat/
│       ├── __init__.py
│       ├── models.py        # SQLAlchemy ChatSession + ChatMessage ORM models
│       ├── router.py        # /sessions endpoints
│       └── schemas.py       # Pydantic chat session/message schemas
├── alembic/
│   ├── env.py               # Async Alembic migration environment
│   ├── script.py.mako       # Revision template
│   └── versions/            # Generated migration scripts
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Shared fixtures (in-memory SQLite, mocked bot)
│   ├── test_auth.py         # Auth endpoint tests
│   ├── test_chat.py         # Chat session persistence tests
│   └── test_existing.py     # Tests for /health, /start-session, /chat
├── docs/
│   ├── ec2-deployment-guide.md
│   └── frontend-integration-guide.md
├── alembic.ini
├── pytest.ini
├── requirements.txt
└── .env.example
```

## Quick Start

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd language-tutor
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY, DATABASE_URL, and JWT_SECRET_KEY
```

See the [Environment Variables](#environment-variables) section for all required values.

### 3. Run database migrations

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Requires a running MySQL instance and a valid `DATABASE_URL` in `.env`. The single autogenerate step detects all models (`users`, `chat_sessions`, `chat_messages`) and creates the migration file; `upgrade head` applies it.

### 4. Run the server

```bash
uvicorn main:app --reload
# API docs at http://localhost:8000/docs
```

Or run directly:
```bash
python main.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for GPT-4o-mini and embeddings |
| `DATABASE_URL` | Yes | — | Async DB connection string. Format: `mysql+aiomysql://user:pass@host:port/dbname` |
| `JWT_SECRET_KEY` | Yes | — | Secret used to sign JWTs. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token lifetime in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token lifetime in days |

## API Endpoints

### Auth (no token required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Register a new user; returns user object |
| `POST` | `/auth/login` | Login; returns access token + refresh token |
| `POST` | `/auth/refresh` | Exchange a refresh token for a new access token |
| `GET` | `/auth/me` | Return the currently authenticated user (**requires token**) |

### Tutoring (Bearer token required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — public, no token needed |
| `POST` | `/start-session` | Initialise Lexie's in-memory bot state for a session |
| `POST` | `/chat` | Send a message and get Lexie's reply |

### Chat Sessions (Bearer token required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/sessions` | List the user's sessions, newest first (max 50) |
| `POST` | `/sessions` | Create a new session record; returns `session_id` to pass to `/start-session` |
| `GET` | `/sessions/{session_id}` | Get session metadata and full message history |
| `DELETE` | `/sessions/{session_id}` | Hard-delete a session and all its messages |

All protected endpoints expect the header: `Authorization: Bearer <access_token>`

### Example: register and log in

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Alex", "email": "alex@example.com", "password": "mypassword"}'

curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alex@example.com", "password": "mypassword"}'
# Response: { "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```

### Example: start a session and chat

```bash
TOKEN="<your_access_token>"

curl -X POST http://localhost:8000/start-session \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"session_id": "abc123", "target_language": "Japanese", "user_name": "Alex"}'

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"session_id": "abc123", "message": "How do I say hello?"}'
```

## Running Tests

Tests use an in-memory SQLite database and a mocked bot — no MySQL, OpenAI API key, or ChromaDB instance required.

```bash
pytest tests/ -v
```

32 tests should pass. Run a single file with:
```bash
pytest tests/test_auth.py -v
pytest tests/test_chat.py -v
pytest tests/test_existing.py -v
```

## How the Embeddings Work

Every completed exchange (user message + Lexie's reply) is embedded with `text-embedding-3-small` and stored in a local ChromaDB collection (`./chroma_data/`). On each new turn, the incoming user message is embedded and the 3 most semantically similar past exchanges — **within the same session** — are prepended to the system prompt as background context.

This lets Lexie remember things like "we practised greetings earlier" without needing the entire conversation history in the context window.

To start fresh (clear all stored vectors), delete the `chroma_data/` directory.

## Docs

- [`docs/frontend-integration-guide.md`](docs/frontend-integration-guide.md) — complete guide for frontend developers: auth flow, session lifecycle, all endpoints with request/response schemas, Axios interceptor example, and an end-to-end walkthrough
- [`docs/ec2-deployment-guide.md`](docs/ec2-deployment-guide.md) — AWS EC2 deployment: launch instance, SSH, systemd service, and gotchas

## Deployment

To run Lexie on AWS EC2, see [`docs/ec2-deployment-guide.md`](docs/ec2-deployment-guide.md).

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI |
| AI model | OpenAI `gpt-4o-mini` |
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector database | ChromaDB (local persistent) |
| Auth | `python-jose` (JWT) + `bcrypt` (direct) |
| Database | MySQL via SQLAlchemy async (`aiomysql`) |
| Migrations | Alembic |
| Env management | python-dotenv |
| Server | Uvicorn |
| Testing | pytest + pytest-asyncio + httpx |

# Language Tutor Chatbot — Lexie

A friendly, text-based language tutor chatbot built with **FastAPI**, **GPT-4o-mini**, and **ChromaDB**. Meet **Lexie** — short for *lexicon* — your patient, encouraging AI language tutor.

## Features

- Secure JWT-based authentication — register, log in, and access tutoring with a Bearer token
- Introduce yourself to Lexie and tell her which language you want to learn
- She remembers your conversation within a session and adapts to your level
- Past exchanges are stored as embeddings in ChromaDB and retrieved as context, so Lexie stays relevant across a long session
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
│   └── auth/
│       ├── dependencies.py  # get_current_user() FastAPI dependency
│       ├── models.py        # SQLAlchemy User ORM model
│       ├── router.py        # /auth endpoints
│       ├── schemas.py       # Pydantic auth request/response schemas
│       └── service.py       # Password hashing, JWT logic, DB queries
├── alembic/
│   ├── env.py               # Async Alembic migration environment
│   ├── script.py.mako       # Revision template
│   └── versions/            # Generated migration scripts
├── tests/
│   ├── conftest.py          # Shared fixtures (in-memory SQLite, mocked bot)
│   ├── test_auth.py         # Auth endpoint tests
│   └── test_existing.py     # Tests for /health, /start-session, /chat
├── docs/
│   └── ec2-deployment-guide.md
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
alembic revision --autogenerate -m "create users table"
alembic upgrade head
```

Requires a running MySQL instance and a valid `DATABASE_URL` in `.env`.

### 4. Run the server

```bash
uvicorn main:app --reload
# API docs at http://localhost:8000/docs
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
| `POST` | `/start-session` | Open a new tutoring session |
| `POST` | `/chat` | Send a message and get Lexie's reply |

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

16 tests should pass. Run a single file with:
```bash
pytest tests/test_auth.py -v
pytest tests/test_existing.py -v
```

## How the Embeddings Work

Every completed exchange (user message + Lexie's reply) is embedded with `text-embedding-3-small` and stored in a local ChromaDB collection (`./chroma_data/`). On each new turn, the incoming user message is embedded and the 3 most semantically similar past exchanges — **within the same session** — are prepended to the system prompt as background context.

This lets Lexie remember things like "we practised greetings earlier" without needing the entire conversation history in the context window.

To start fresh (clear all stored vectors), delete the `chroma_data/` directory.

## Deployment

To run Lexie on AWS EC2, see the step-by-step guides in [`docs/`](docs/):

- [`ec2-deployment-guide.md`](docs/ec2-deployment-guide.md) — full walkthrough: launch instance, SSH, systemd service, and gotchas

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI |
| AI model | OpenAI `gpt-4o-mini` |
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector database | ChromaDB (local persistent) |
| Auth | `python-jose` (JWT) + `passlib[bcrypt]` |
| Database | MySQL via SQLAlchemy async (`aiomysql`) |
| Migrations | Alembic |
| Env management | python-dotenv |
| Server | Uvicorn |
| Testing | pytest + pytest-asyncio + httpx |

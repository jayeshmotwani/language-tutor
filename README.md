# Language Tutor Chatbot — Lexie

A friendly, text-based language tutor chatbot built with **FastAPI**, **GPT-4o-mini**, and **ChromaDB**. Meet **Lexie** — short for *lexicon* — your patient, encouraging AI language tutor.

## Features

- Introduce yourself to Lexie and tell her which language you want to learn
- She remembers your conversation within a session and adapts to your level
- Past exchanges are stored as embeddings in ChromaDB and retrieved as context, so Lexie stays relevant across a long session
- Clean OOP design: `LanguageTutorBot`, `EmbeddingService`, `SessionManager`

## Project Structure

```
language-tutor/
├── app/
│   ├── __init__.py
│   ├── bot.py          # LanguageTutorBot — orchestrates chat logic
│   ├── embeddings.py   # EmbeddingService — ChromaDB + OpenAI embeddings
│   ├── models.py       # Pydantic request/response schemas
│   └── session.py      # SessionManager — in-memory session state
├── main.py             # FastAPI app + endpoint definitions
├── requirements.txt
├── .env.example
└── .gitignore
```

## Quick Start

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd language-tutor
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set your OpenAI API key

```bash
cp .env.example .env
# Edit .env and add your key:
#   OPENAI_API_KEY=sk-...
```

### 3. Run the server

```bash
uvicorn main:app --reload
# API docs at http://localhost:8000/docs
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — confirms the service is running |
| `POST` | `/start-session` | Open a new tutoring session |
| `POST` | `/chat` | Send a message and get Lexie's reply |

### Example: start a session

```bash
curl -X POST http://localhost:8000/start-session \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123", "target_language": "Japanese", "user_name": "Alex"}'
```

### Example: chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123", "message": "How do I say hello?"}'
```

## How the Embeddings Work

Every completed exchange (user message + Lexie's reply) is embedded with `text-embedding-3-small` and stored in a local ChromaDB collection (`./chroma_data/`). On each new turn, the incoming user message is embedded and the 3 most semantically similar past exchanges — **within the same session** — are prepended to the system prompt as background context.

This lets Lexie remember things like "we practised greetings earlier" without needing the entire conversation history in the context window.

To start fresh (clear all stored vectors), delete the `chroma_data/` directory.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI |
| AI model | OpenAI `gpt-4o-mini` |
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector database | ChromaDB (local persistent) |
| Env management | python-dotenv |
| Server | Uvicorn |

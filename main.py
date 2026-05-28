"""
main.py — FastAPI entry point for the Language Tutor Chatbot.

Run locally with:
    uvicorn main:app --reload

Or directly:
    python main.py
"""

import os

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.auth.dependencies import get_current_user
from app.auth.models import User  # noqa: F401 — ensures model is registered with Base
from app.auth.router import router as auth_router
from app.bot import LanguageTutorBot
from app.models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    StartSessionRequest,
    StartSessionResponse,
)

# Load OPENAI_API_KEY (and any other vars) from .env before anything else.
load_dotenv()

# ── App initialisation ────────────────────────────────────────────────────────

app = FastAPI(
    title="Language Tutor Chatbot — Lexie",
    description=(
        "A friendly AI-powered language tutor powered by GPT-4o-mini and ChromaDB. "
        "Start a session, pick your language, and start chatting!"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "Authorization"],
)

app.include_router(auth_router)

# Validate that the API key is present before the server starts accepting traffic.
_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. "
        "Copy .env.example to .env and add your key."
    )

# Single bot instance shared across all requests (thread-safe for reads;
# in-memory session state is sufficient for this POC).
bot = LanguageTutorBot(openai_api_key=_api_key)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Utility"])
def health_check() -> HealthResponse:
    """Confirm the service is up and return the bot's name."""
    return HealthResponse(status="ok", bot_name=LanguageTutorBot.BOT_NAME)


@app.post("/start-session", response_model=StartSessionResponse, tags=["Session"])
async def start_session(
    request: StartSessionRequest,
    _: User = Depends(get_current_user),
) -> StartSessionResponse:
    """
    Initialise a new tutoring session. Requires Bearer token.

    - **session_id**: a unique string you generate (e.g. a UUID).
    - **target_language**: the language to learn (e.g. "Japanese").
    - **user_name**: optional; used in the greeting if provided.

    Returns Lexie's opening message and confirms the active language.
    """
    try:
        welcome = bot.start_session(
            session_id=request.session_id,
            target_language=request.target_language,
            user_name=request.user_name,
        )
        return StartSessionResponse(
            session_id=request.session_id,
            message=welcome,
            language=request.target_language,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not start session: {exc}")


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(
    request: ChatRequest,
    _: User = Depends(get_current_user),
) -> ChatResponse:
    """
    Send a message to Lexie and receive her reply. Requires Bearer token.

    - **session_id**: must match a session created via POST /start-session.
    - **message**: the learner's text input.

    Returns Lexie's response along with the session ID and active language.
    """
    try:
        reply = bot.chat(
            session_id=request.session_id,
            user_message=request.message,
        )
        session = bot.session_manager.get_session(request.session_id)
        return ChatResponse(
            session_id=request.session_id,
            response=reply,
            language=session.target_language,
        )
    except ValueError as exc:
        # Session not found — 404 is the right status code here.
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat error: {exc}")


# ── Dev server ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

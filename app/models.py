"""
Pydantic models that define the shape of API request and response bodies.
FastAPI uses these models to validate incoming data and serialize outgoing data.
"""

from pydantic import BaseModel
from typing import Optional


# ── Request models ────────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    """Body sent by the client to open a new tutoring session."""
    session_id: str          # Caller-supplied unique ID (e.g. UUID)
    target_language: str     # Language the user wants to learn (e.g. "Spanish")
    user_name: Optional[str] = None  # Optional first name for personalised greetings


class ChatRequest(BaseModel):
    """Body sent by the client for each chat turn."""
    session_id: str   # Must match a previously started session
    message: str      # The user's message text


# ── Response models ───────────────────────────────────────────────────────────

class StartSessionResponse(BaseModel):
    """Returned when a session is successfully created."""
    session_id: str
    message: str      # Lexie's opening greeting
    language: str     # Confirmed target language


class ChatResponse(BaseModel):
    """Returned for each chat turn."""
    session_id: str
    response: str     # Lexie's reply
    language: str     # Active target language for this session


class HealthResponse(BaseModel):
    """Simple health-check payload."""
    status: str
    bot_name: str

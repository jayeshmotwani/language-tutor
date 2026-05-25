"""
Session management: stores each user's target language and conversation history
entirely in memory for the lifetime of the server process.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Session:
    """
    Holds all state for a single tutoring session.

    Attributes:
        session_id:             Unique identifier supplied by the caller.
        target_language:        The language the user wants to learn.
        user_name:              Optional first name used in greetings.
        conversation_history:   Ordered list of {role, content} dicts passed
                                directly to the OpenAI chat API.
        is_first_message:       True until the bot has sent its opening greeting;
                                used to decide whether to inject the introduction.
    """
    session_id: str
    target_language: str
    user_name: Optional[str]
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    is_first_message: bool = True


class SessionManager:
    """
    Creates, retrieves, and updates Session objects.

    All data lives in a plain dictionary keyed by session_id.
    There is intentionally no persistence — this is a POC.
    """

    # How many recent messages to keep in the context window.
    # Older messages are dropped to avoid hitting token limits.
    MAX_HISTORY_MESSAGES = 20

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    # ── Public interface ──────────────────────────────────────────────────────

    def create_session(
        self,
        session_id: str,
        target_language: str,
        user_name: Optional[str] = None,
    ) -> Session:
        """Create (or reset) a session and return it."""
        session = Session(
            session_id=session_id,
            target_language=target_language,
            user_name=user_name,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Return the session object, or None if it does not exist."""
        return self._sessions.get(session_id)

    def session_exists(self, session_id: str) -> bool:
        """Quick existence check without returning the full object."""
        return session_id in self._sessions

    def add_to_history(self, session_id: str, role: str, content: str) -> None:
        """
        Append a message to the session's conversation history and enforce
        the MAX_HISTORY_MESSAGES cap to keep context manageable.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.conversation_history.append({"role": role, "content": content})
        # Trim oldest messages when the window grows too large
        if len(session.conversation_history) > self.MAX_HISTORY_MESSAGES:
            session.conversation_history = session.conversation_history[
                -self.MAX_HISTORY_MESSAGES :
            ]

    def mark_first_message_done(self, session_id: str) -> None:
        """Called after the bot sends its opening greeting."""
        session = self._sessions.get(session_id)
        if session:
            session.is_first_message = False

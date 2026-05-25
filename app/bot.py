"""
LanguageTutorBot: the heart of the application.

This class owns the OpenAI chat client, the EmbeddingService, and the
SessionManager. All business logic — building prompts, calling GPT-4o-mini,
storing results — lives here.
"""

from openai import OpenAI
from typing import Optional

from app.embeddings import EmbeddingService
from app.session import Session, SessionManager


class LanguageTutorBot:
    """
    Orchestrates a language-tutoring conversation.

    Typical flow:
      1. Caller calls `start_session(...)` once per learner.
      2. Caller calls `chat(session_id, message)` for every user turn.
         The method:
           a. Fetches semantically relevant past exchanges from ChromaDB.
           b. Builds a system prompt that sets Lexie's persona and language goal.
           c. Sends the full conversation history to GPT-4o-mini.
           d. Stores the new exchange in ChromaDB for future retrieval.
           e. Returns the bot's reply text.

    Lexie is the bot's name — a playful nod to "lexicon" (the vocabulary of a
    language) — chosen to feel approachable and memorable.
    """

    # Public constant so the FastAPI layer can reference the name without
    # needing a bot instance.
    BOT_NAME = "Lexie"

    # System-level personality injected at the top of every API call.
    _PERSONA = (
        f"You are {BOT_NAME}, a warm, encouraging, and endlessly patient "
        "language tutor. You celebrate every small win, never make the learner "
        "feel embarrassed about mistakes, and explain things in a friendly, "
        "conversational tone — like a knowledgeable friend rather than a "
        "textbook. Keep replies focused and easy to read; avoid walls of text."
    )

    def __init__(self, openai_api_key: str, chroma_persist_path: str = "./chroma_data") -> None:
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.embedding_service = EmbeddingService(
            openai_client=self.openai_client,
            persist_path=chroma_persist_path,
        )
        self.session_manager = SessionManager()

    # ── Public interface ──────────────────────────────────────────────────────

    def start_session(
        self,
        session_id: str,
        target_language: str,
        user_name: Optional[str] = None,
    ) -> str:
        """
        Create a new session and return Lexie's opening greeting.

        The greeting is stored in conversation history so GPT-4o-mini is
        aware that the introduction has already been given.
        """
        self.session_manager.create_session(
            session_id=session_id,
            target_language=target_language,
            user_name=user_name,
        )

        name_part = f", {user_name}" if user_name else ""
        welcome = (
            f"Hi{name_part}! I'm {self.BOT_NAME}, your personal language tutor! "
            f"I'm really excited to help you learn {target_language}. "
            f"We'll go completely at your pace — no pressure, just progress. "
            f"So, where would you like to begin? "
            f"Everyday greetings, useful phrases, pronunciation tips, grammar basics? "
            f"Just tell me, and we'll dive right in!"
        )

        # Record the greeting so future API calls see it in the message list.
        self.session_manager.add_to_history(session_id, "assistant", welcome)
        self.session_manager.mark_first_message_done(session_id)

        return welcome

    def chat(self, session_id: str, user_message: str) -> str:
        """
        Process one user message and return Lexie's reply.

        Raises:
            ValueError: if session_id has not been initialised via start_session.
        """
        session = self.session_manager.get_session(session_id)
        if session is None:
            raise ValueError(
                f"Session '{session_id}' not found. "
                "Please call POST /start-session first."
            )

        # Pull semantically relevant past exchanges to enrich the system prompt.
        context = self.embedding_service.retrieve_relevant_context(
            query=user_message,
            session_id=session_id,
        )

        system_prompt = self._build_system_prompt(session, context)

        # Append the new user turn to history before calling the API so the
        # model sees the full, up-to-date conversation.
        self.session_manager.add_to_history(session_id, "user", user_message)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(session.conversation_history)

        api_response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,    # A touch of warmth without being erratic
            max_tokens=600,
        )

        bot_reply = api_response.choices[0].message.content.strip()

        # Persist the exchange in both the in-memory history and ChromaDB.
        self.session_manager.add_to_history(session_id, "assistant", bot_reply)
        self.embedding_service.store_exchange(
            session_id=session_id,
            user_message=user_message,
            bot_response=bot_reply,
            language=session.target_language,
        )

        return bot_reply

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_system_prompt(self, session: Session, context: str) -> str:
        """
        Compose the system prompt from the fixed persona, the active language,
        teaching guidelines, and any retrieved context from ChromaDB.
        """
        prompt = (
            f"{self._PERSONA}\n\n"
            f"The learner is currently studying: **{session.target_language}**\n\n"
            "Teaching guidelines:\n"
            f"- Write example phrases and vocabulary in {session.target_language} "
            "and always include an English translation in parentheses.\n"
            "- Gently point out and correct mistakes without dwelling on them.\n"
            "- Match your explanation depth to the learner's apparent level.\n"
            "- Keep each reply concise — aim for 2-4 short paragraphs max.\n"
            "- End with a small prompt or question to keep the conversation going.\n"
        )

        if context:
            prompt += (
                "\nRelevant previous exchanges (use as background context, "
                "do not repeat verbatim):\n"
                + context
                + "\n"
            )

        return prompt

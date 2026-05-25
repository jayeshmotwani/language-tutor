"""
EmbeddingService: wraps OpenAI text-embedding-3-small and ChromaDB to store
past conversation exchanges and retrieve the most relevant ones as context
for the current user message.
"""

import chromadb
from openai import OpenAI
from typing import List


class EmbeddingService:
    """
    Handles all vector-database operations for the language tutor.

    Workflow per chat turn:
      1. `retrieve_relevant_context(query, session_id)` — embed the incoming
         user message, query ChromaDB for the N most similar past exchanges
         *within the same session*, and return them as plain text.
      2. After the bot replies, `store_exchange(...)` — embed the combined
         "User: … / Tutor: …" text and upsert it into ChromaDB.

    Using session_id as a metadata filter keeps each learner's history
    isolated from others sharing the same server instance.
    """

    EMBEDDING_MODEL = "text-embedding-3-small"

    def __init__(self, openai_client: OpenAI, persist_path: str = "./chroma_data") -> None:
        self.openai_client = openai_client

        # PersistentClient saves vectors to disk so they survive server restarts.
        # Change to chromadb.EphemeralClient() if you prefer fully in-memory.
        self.chroma_client = chromadb.PersistentClient(path=persist_path)

        # One collection stores all sessions; filtering happens via metadata.
        self.collection = self.chroma_client.get_or_create_collection(
            name="language_tutor_exchanges",
            metadata={"hnsw:space": "cosine"},  # cosine similarity for semantic search
        )

    # ── Public interface ──────────────────────────────────────────────────────

    def store_exchange(
        self,
        session_id: str,
        user_message: str,
        bot_response: str,
        language: str,
    ) -> None:
        """
        Embed and store a completed exchange (user turn + bot reply) so it
        can be surfaced later as relevant context.
        """
        document = f"User: {user_message}\nTutor: {bot_response}"
        embedding = self._embed(document)

        # Use a combination of session_id and current count for a unique doc ID.
        doc_id = f"{session_id}_{self.collection.count()}"

        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[document],
            metadatas=[{"session_id": session_id, "language": language}],
        )

    def retrieve_relevant_context(
        self,
        query: str,
        session_id: str,
        n_results: int = 3,
    ) -> str:
        """
        Return the top-N most semantically similar past exchanges for this
        session as a single newline-separated string, or "" if none exist yet.
        """
        total_docs = self.collection.count()
        if total_docs == 0:
            return ""

        try:
            query_embedding = self._embed(query)
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, total_docs),
                where={"session_id": session_id},
            )
            documents = results.get("documents", [[]])[0]
            return "\n\n".join(documents) if documents else ""
        except Exception:
            # Retrieval is best-effort; never crash the chat turn because of it.
            return ""

    # ── Private helpers ───────────────────────────────────────────────────────

    def _embed(self, text: str) -> List[float]:
        """Call the OpenAI embeddings API and return the raw vector."""
        response = self.openai_client.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding

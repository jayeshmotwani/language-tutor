# Chat Sessions Integration Guide — Lexie Language Tutor API

This guide covers only the persistent session storage APIs added to the Lexie backend: the `/sessions` endpoints and the message-persistence behaviour of `/start-session` and `/chat`. For authentication and the full API overview, see [`frontend-integration-guide.md`](frontend-integration-guide.md).

All endpoints in this guide require a Bearer token: `Authorization: Bearer <access_token>`.

---

## 1. Overview

The chat session layer gives users a persistent conversation history, similar to ChatGPT's sidebar. There are two complementary layers:

| Layer | Endpoints | Purpose |
|-------|-----------|---------|
| Persistence | `POST /sessions`, `GET /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}` | Store and retrieve sessions and messages in MySQL |
| Bot | `POST /start-session`, `POST /chat` | Run the live tutoring conversation in memory |

Both layers share the same `session_id`. You create the record first, then pass the same ID to the bot endpoints.

---

## 2. Data Models

### ChatSession

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | Session identifier — you supply this when calling `/start-session` |
| `language` | string | Target language |
| `title` | string \| null | Auto-generated from the first user message; null until the first `/chat` call |
| `created_at` | datetime | When the session was created |
| `updated_at` | datetime | Updated on every `/chat` call |

### ChatMessage

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Message ID |
| `role` | string | `"user"` or `"assistant"` |
| `content` | string | Message text |
| `created_at` | datetime | When the message was saved |

---

## 3. Endpoint Reference

### `POST /sessions` — Create a session

Creates a new session record and returns a `session_id` to use with all subsequent calls.

**Request**

```http
POST /sessions
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "language": "Japanese"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | string | Yes | Target language (e.g. `"Japanese"`) |

**Response `201 Created`**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "Japanese",
  "title": null,
  "created_at": "2026-05-30T09:05:00",
  "updated_at": "2026-05-30T09:05:00"
}
```

`title` is always `null` on creation — it is set automatically when the user sends their first message via `POST /chat`.

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Not authenticated` | Missing or invalid token |
| `422` | Validation error | `language` field missing or wrong type |

---

### `GET /sessions` — List sessions

Returns up to 50 of the authenticated user's sessions, ordered by `updated_at` descending (most recently active first).

**Request**

```http
GET /sessions
Authorization: Bearer <access_token>
```

**Response `200 OK`**

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "language": "Japanese",
    "title": "How do I say 'thank you'?",
    "created_at": "2026-05-30T09:05:00",
    "updated_at": "2026-05-30T09:08:00"
  },
  {
    "id": "661f9511-f3ac-52e5-b827-557766551111",
    "language": "Spanish",
    "title": null,
    "created_at": "2026-05-29T14:00:00",
    "updated_at": "2026-05-29T14:00:00"
  }
]
```

Returns an empty array `[]` if the user has no sessions.

`title` may be `null` if the session was created but `/chat` was never called. Show `language` as a fallback label in the sidebar.

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Not authenticated` | Missing or invalid token |

---

### `GET /sessions/{session_id}` — Get session detail

Returns session metadata plus the complete message history, ordered oldest first.

**Request**

```http
GET /sessions/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <access_token>
```

**Response `200 OK`**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "Japanese",
  "title": "How do I say 'thank you'?",
  "created_at": "2026-05-30T09:05:00",
  "updated_at": "2026-05-30T09:08:00",
  "messages": [
    {
      "id": 1,
      "role": "assistant",
      "content": "こんにちは Alex! I'm Lexie, your Japanese tutor. What would you like to learn today?",
      "created_at": "2026-05-30T09:05:00"
    },
    {
      "id": 2,
      "role": "user",
      "content": "How do I say 'thank you'?",
      "created_at": "2026-05-30T09:07:00"
    },
    {
      "id": 3,
      "role": "assistant",
      "content": "In Japanese, 'thank you' is ありがとう (arigatou). A more formal version is ありがとうございます (arigatou gozaimasu).",
      "created_at": "2026-05-30T09:07:01"
    }
  ]
}
```

The first message is always the assistant greeting saved by `/start-session`. Messages alternate `assistant → user → assistant` from there.

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Not authenticated` | Missing or invalid token |
| `404` | `Session not found` | Session does not exist or belongs to a different user |

---

### `DELETE /sessions/{session_id}` — Delete a session

Hard-deletes the session and all its messages. This is irreversible.

**Request**

```http
DELETE /sessions/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <access_token>
```

**Response `204 No Content`** — empty body.

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Not authenticated` | Missing or invalid token |
| `404` | `Session not found` | Session does not exist or belongs to a different user |

---

## 4. Persistence Behaviour of `/start-session` and `/chat`

These endpoints are unchanged from a request/response perspective — the persistence happens as a side-effect.

### `POST /start-session` — what it persists

- If no `chat_sessions` row exists yet for the given `session_id`, one is created (using `language` from the request body and the authenticated user's ID).
- Lexie's greeting is saved as a `ChatMessage` with `role = "assistant"`.

You can call `/start-session` with the same `session_id` multiple times (e.g. when resuming after a page reload) — it will not create a duplicate session record or duplicate the greeting if the row already exists.

### `POST /chat` — what it persists

- The user's message is saved as `role = "user"`.
- Lexie's reply is saved as `role = "assistant"`.
- `ChatSession.updated_at` is set to the current time.
- If `ChatSession.title` is still `null`, it is set to the first 60 characters of the user's message, trimmed cleanly at the last word boundary (never cuts mid-word).

---

## 5. Title Auto-Generation

The session title is derived from the first message the user sends and is never overwritten by subsequent messages.

**Rules:**
- Set on the first `POST /chat` call when the session title is `null`.
- Trimmed to a maximum of 60 characters.
- Trimming always cuts at the last space — words are never split.

**Examples:**

| User message | Resulting title |
|---|---|
| `"How do I say 'thank you'?"` | `"How do I say 'thank you'?"` (under 60 chars, no trim) |
| `"Can you please teach me how to conjugate verbs in the present tense"` | `"Can you please teach me how to conjugate verbs in the"` (trimmed at last space ≤ 60 chars) |

In the sidebar, display `title` once it is set. While it is `null`, fall back to `language`.

---

## 6. Session Lifecycle

```
POST /sessions          → creates DB record, returns session_id
        │
        ▼
POST /start-session     → initialises bot in memory, saves greeting message
        │
        ▼
POST /chat  (×N)        → saves user + assistant messages, sets title on first call
        │
        ▼
GET /sessions           → list for sidebar (updated_at reflects last activity)
GET /sessions/{id}      → full history for resuming or display
DELETE /sessions/{id}   → remove from sidebar, cascade-deletes all messages
```

### Starting a brand-new session

```js
// 1. Create the DB record
const { data: session } = await api.post('/sessions', { language: 'Japanese' });
const sessionId = session.id;

// 2. Initialise the bot
const { data: start } = await api.post('/start-session', {
  session_id: sessionId,
  target_language: 'Japanese',
  user_name: 'Alex',
});

// Display start.message as Lexie's first bubble
```

### Resuming a session after page reload

```js
// 1. Fetch history to populate the chat view
const { data: detail } = await api.get(`/sessions/${sessionId}`);
renderMessages(detail.messages);

// 2. Re-initialise the bot (discard the greeting — history is already shown)
await api.post('/start-session', {
  session_id: sessionId,
  target_language: detail.language,
});
```

### Sending a message

```js
const { data } = await api.post('/chat', {
  session_id: sessionId,
  message: userInput,
});

// data.response is Lexie's reply
// If this was the first message, refresh the sidebar entry to pick up the new title
```

### Loading the sidebar

```js
const { data: sessions } = await api.get('/sessions');
// sessions[0] is the most recently active
// Use session.title ?? session.language as the display label
```

### Deleting a session

```js
await api.delete(`/sessions/${sessionId}`);
// Remove from sidebar state; clear the chat view if it was open
```

---

## 7. Error Handling

| Status | Cause | Recommended action |
|--------|-------|-------------------|
| `401` | Token missing, expired, or invalid | Attempt silent refresh; redirect to login if refresh fails |
| `404` | Session not found or belongs to another user | Remove stale sidebar entry; show "not found" message |
| `422` | Malformed request body (e.g. missing `language`) | Fix the request — the response body lists which fields failed |
| `500` | Bot error on `/start-session` or `/chat` | Show a generic error; the session record is unaffected |

# Frontend Integration Guide — Lexie Language Tutor API

This guide walks through everything a frontend developer needs to integrate with the Lexie backend: authentication, session management, chat, and history. Examples use consistent data throughout so you can follow one user's full journey end-to-end.

---

## 1. Overview

Lexie is a FastAPI backend that provides JWT-authenticated language tutoring via a chat interface. Sessions and messages are persisted to MySQL so users can resume past conversations, similar to ChatGPT's sidebar history.

### Base URLs

| Environment | URL |
|-------------|-----|
| Local development | `http://localhost:8000` |
| Production (EC2) | `https://your-domain.com` (configure per deployment) |

### Authentication

All tutoring and session endpoints require a **JWT Bearer token** in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Tokens are obtained by logging in via `POST /auth/login`. Access tokens expire after 30 minutes by default; use the refresh token to obtain a new one without re-entering credentials.

---

## 2. Authentication Flow

### Which endpoints are public vs. protected

| Endpoint | Auth required |
|----------|--------------|
| `GET /health` | No |
| `POST /auth/register` | No |
| `POST /auth/login` | No |
| `POST /auth/refresh` | No |
| `GET /auth/me` | **Yes** |
| All `/sessions/*` | **Yes** |
| `POST /start-session` | **Yes** |
| `POST /chat` | **Yes** |

### Step-by-step

#### Step 1 — Register

```http
POST /auth/register
Content-Type: application/json

{
  "name": "Alex Chen",
  "email": "alex@example.com",
  "password": "supersecret123"
}
```

Response `201 Created`:

```json
{
  "id": 1,
  "name": "Alex Chen",
  "email": "alex@example.com",
  "created_at": "2026-05-30T09:00:00",
  "is_active": true
}
```

#### Step 2 — Login

```http
POST /auth/login
Content-Type: application/json

{
  "email": "alex@example.com",
  "password": "supersecret123"
}
```

Response `200 OK`:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Step 3 — Store tokens

```js
localStorage.setItem('access_token', data.access_token);
localStorage.setItem('refresh_token', data.refresh_token);
```

#### Step 4 — Attach to every protected request

```js
const authHeaders = {
  Authorization: `Bearer ${localStorage.getItem('access_token')}`,
};
```

#### Step 5 — Fetch the current user (optional, good for confirming token validity on page load)

```http
GET /auth/me
Authorization: Bearer <access_token>
```

Response `200 OK`:

```json
{
  "id": 1,
  "name": "Alex Chen",
  "email": "alex@example.com",
  "created_at": "2026-05-30T09:00:00",
  "is_active": true
}
```

#### Step 6 — Refresh an expired access token

When any protected request returns `401`, swap the refresh token for a new access token:

```http
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

Response `200 OK`:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Store the new access token and retry the original request. If the refresh call also returns `401`, the refresh token has expired — redirect to login.

#### Step 7 — Logout

There is no server-side logout endpoint. Clear local storage:

```js
localStorage.removeItem('access_token');
localStorage.removeItem('refresh_token');
```

---

## 3. Chat Session Flow

A session has two distinct layers:

- **Persistent layer** (`/sessions`) — the DB record. Holds the history you show in the sidebar.
- **Bot layer** (`/start-session`, `/chat`) — the in-memory state Lexie needs to hold a live conversation.

Both must be initialised before the user can chat. Here is the full happy path:

### Step 1 — Create a session record

```http
POST /sessions
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "language": "Japanese"
}
```

Response `201 Created`:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "Japanese",
  "title": null,
  "created_at": "2026-05-30T09:05:00",
  "updated_at": "2026-05-30T09:05:00"
}
```

Store the `id` — you will pass it as `session_id` to every subsequent call.

### Step 2 — Initialise Lexie

```http
POST /start-session
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "target_language": "Japanese",
  "user_name": "Alex"
}
```

`user_name` is optional. When provided, Lexie uses it in her greeting.

Response `200 OK`:

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "こんにちは Alex! I'm Lexie, your Japanese tutor. What would you like to learn today?",
  "language": "Japanese"
}
```

Display `message` as Lexie's first chat bubble. This greeting is automatically saved to the session's message history.

### Step 3 — Send messages

```http
POST /chat
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "How do I say 'thank you'?"
}
```

Response `200 OK`:

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "response": "In Japanese, 'thank you' is ありがとう (arigatou). A more formal version is ありがとうございます (arigatou gozaimasu).",
  "language": "Japanese"
}
```

Both the user message and Lexie's reply are automatically persisted. The session's `title` is set to the first 60 characters of the user's first message (trimmed at the last word boundary).

### Step 4 — Load past sessions (sidebar)

```http
GET /sessions
Authorization: Bearer <access_token>
```

Response `200 OK` — up to 50 sessions, newest first:

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "language": "Japanese",
    "title": "How do I say 'thank you'?",
    "created_at": "2026-05-30T09:05:00",
    "updated_at": "2026-05-30T09:07:00"
  }
]
```

Use `title` as the sidebar label. Fall back to `language` if `title` is still `null` (session was created but no message was sent yet).

### Step 5 — Resume a session

Resuming requires two calls: fetch the history, then re-initialise the bot.

**Fetch message history:**

```http
GET /sessions/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <access_token>
```

Response `200 OK`:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "Japanese",
  "title": "How do I say 'thank you'?",
  "created_at": "2026-05-30T09:05:00",
  "updated_at": "2026-05-30T09:07:00",
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
      "content": "In Japanese, 'thank you' is ありがとう (arigatou)...",
      "created_at": "2026-05-30T09:07:01"
    }
  ]
}
```

Render `messages` to populate the chat view. `role` is either `"user"` or `"assistant"`.

**Re-initialise the bot** (so Lexie can continue the conversation in memory):

```http
POST /start-session
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "target_language": "Japanese"
}
```

Do **not** display the greeting that comes back — the chat view is already populated from the history you loaded above. Just discard the response or ignore the `message` field.

### Step 6 — Delete a session

```http
DELETE /sessions/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <access_token>
```

Response: `204 No Content` (empty body). All messages cascade-delete automatically. Remove the entry from your sidebar state.

---

## 4. Complete Endpoint Reference

### Endpoint summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | Health check |
| `POST` | `/auth/register` | No | Create a new user account |
| `POST` | `/auth/login` | No | Login; returns access + refresh tokens |
| `POST` | `/auth/refresh` | No | Exchange refresh token for a new access token |
| `GET` | `/auth/me` | Yes | Return the current authenticated user |
| `GET` | `/sessions` | Yes | List the user's sessions (newest first, max 50) |
| `POST` | `/sessions` | Yes | Create a new session record |
| `GET` | `/sessions/{session_id}` | Yes | Get session metadata + full message history |
| `DELETE` | `/sessions/{session_id}` | Yes | Hard-delete session and all its messages |
| `POST` | `/start-session` | Yes | Initialise Lexie's in-memory bot state |
| `POST` | `/chat` | Yes | Send a message and receive Lexie's reply |

---

### `POST /auth/register`

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name (1–100 chars) |
| `email` | string | Yes | Valid email address |
| `password` | string | Yes | Minimum 8 characters |

**Response `201`**

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | User ID |
| `name` | string | Display name |
| `email` | string | Email address |
| `created_at` | datetime | Account creation timestamp |
| `is_active` | boolean | Always `true` on registration |

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `400` | `Email already registered` | Duplicate email |

---

### `POST /auth/login`

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | Registered email |
| `password` | string | Yes | Account password |

**Response `200`**

| Field | Type | Description |
|-------|------|-------------|
| `access_token` | string | Short-lived JWT (default 30 min) |
| `refresh_token` | string | Long-lived JWT (default 7 days) |
| `token_type` | string | Always `"bearer"` |

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Incorrect email or password` | Wrong credentials |

---

### `POST /auth/refresh`

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refresh_token` | string | Yes | The refresh token from login |

**Response `200`**

| Field | Type | Description |
|-------|------|-------------|
| `access_token` | string | Fresh access token |
| `token_type` | string | Always `"bearer"` |

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Invalid or expired refresh token` | Token expired, malformed, or wrong type |

---

### `GET /auth/me`

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`** — same shape as the register response.

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Not authenticated` | Missing or invalid token |

---

### `GET /sessions`

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`** — array of session summaries, ordered by `updated_at` descending, capped at 50.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | Session identifier |
| `language` | string | Target language |
| `title` | string \| null | Auto-generated from first user message |
| `created_at` | datetime | When the session was created |
| `updated_at` | datetime | When the last message was sent |

---

### `POST /sessions`

**Headers:** `Authorization: Bearer <access_token>`

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | string | Yes | Target language (e.g. `"Japanese"`) |

**Response `201`** — same shape as a session summary (see above). `title` is always `null` on creation.

---

### `GET /sessions/{session_id}`

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | Session identifier |
| `language` | string | Target language |
| `title` | string \| null | Session title |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last activity timestamp |
| `messages` | array | Full message history (see below) |

Each message object:

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Message ID |
| `role` | string | `"user"` or `"assistant"` |
| `content` | string | Message text |
| `created_at` | datetime | When the message was saved |

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Not authenticated` | Missing or invalid token |
| `404` | `Session not found` | Session does not exist or belongs to another user |

---

### `DELETE /sessions/{session_id}`

**Headers:** `Authorization: Bearer <access_token>`

**Response:** `204 No Content` (empty body).

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Not authenticated` | Missing or invalid token |
| `404` | `Session not found` | Session does not exist or belongs to another user |

---

### `POST /start-session`

**Headers:** `Authorization: Bearer <access_token>`

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | Yes | Must match the `id` from `POST /sessions` |
| `target_language` | string | Yes | Language to learn |
| `user_name` | string | No | Used in Lexie's greeting |

**Response `200`**

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Echoed back |
| `message` | string | Lexie's opening message |
| `language` | string | Active language |

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Not authenticated` | Missing or invalid token |
| `500` | `Could not start session: ...` | Internal bot error |

---

### `POST /chat`

**Headers:** `Authorization: Bearer <access_token>`

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | Yes | Must match an initialised session |
| `message` | string | Yes | The user's message to Lexie |

**Response `200`**

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Echoed back |
| `response` | string | Lexie's reply |
| `language` | string | Active language |

**Errors**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `Not authenticated` | Missing or invalid token |
| `404` | `Session ... not found` | `/start-session` was not called first |
| `500` | `Chat error: ...` | Internal bot error |

---

## 5. Token Strategy

### Access token vs. refresh token

| | Access token | Refresh token |
|--|---|---|
| Lifetime | 30 minutes (default) | 7 days (default) |
| Used for | Every API request | Obtaining new access tokens only |
| Where to store | `localStorage` | `localStorage` |

### Recommended storage

```js
// After login
localStorage.setItem('access_token', tokens.access_token);
localStorage.setItem('refresh_token', tokens.refresh_token);

// On logout or auth failure
localStorage.removeItem('access_token');
localStorage.removeItem('refresh_token');
```

### Silent refresh with Axios interceptors

Set up a response interceptor that transparently refreshes the access token on `401` and retries the original request:

```js
import axios from 'axios';

const api = axios.create({ baseURL: 'http://localhost:8000' });

// Attach access token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Refresh on 401, retry once
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retried) {
      original._retried = true;
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) return redirectToLogin();
      try {
        const { data } = await axios.post('/auth/refresh', {
          refresh_token: refreshToken,
        });
        localStorage.setItem('access_token', data.access_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch {
        return redirectToLogin();
      }
    }
    return Promise.reject(error);
  }
);

function redirectToLogin() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  window.location.href = '/login';
}
```

### When refresh fails

If `POST /auth/refresh` returns `401`, the refresh token itself has expired. Clear both tokens and redirect the user to the login page — there is no further recovery without re-entering credentials.

---

## 6. Error Handling Reference

| Status | Meaning | Recommended action |
|--------|---------|-------------------|
| `400` | Bad request (e.g. duplicate email, validation error) | Show the `detail` message to the user |
| `401` | Unauthenticated — missing, invalid, or expired token | Attempt silent refresh; redirect to login if refresh fails |
| `404` | Resource not found or belongs to another user | Show "not found" UI; remove stale sidebar entry if applicable |
| `422` | Validation error — malformed request body | Fix the request shape; the response body lists which fields failed |
| `500` | Internal server error (bot or DB failure) | Show a generic error message; do not expose `detail` to the end user |

---

## 7. End-to-End Example

This section walks through the complete user journey — from opening the app for the first time to resuming a past session after a page reload.

### First visit — register and start a session

**1. Register**

```http
POST /auth/register
{ "name": "Alex Chen", "email": "alex@example.com", "password": "supersecret123" }
```
→ `201` — user created.

**2. Login**

```http
POST /auth/login
{ "email": "alex@example.com", "password": "supersecret123" }
```
→ `200` — store `access_token` and `refresh_token` in `localStorage`.

**3. Create a session record**

```http
POST /sessions
Authorization: Bearer eyJhbGc...
{ "language": "Japanese" }
```
→ `201`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "Japanese",
  "title": null,
  "created_at": "2026-05-30T09:05:00",
  "updated_at": "2026-05-30T09:05:00"
}
```

Add this session to the sidebar. `title` is null — show `"Japanese"` as a placeholder label until the first message is sent.

**4. Initialise Lexie**

```http
POST /start-session
Authorization: Bearer eyJhbGc...
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "target_language": "Japanese",
  "user_name": "Alex"
}
```
→ `200`

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "こんにちは Alex! I'm Lexie, your Japanese tutor. What would you like to learn today?",
  "language": "Japanese"
}
```

Display `message` as the first chat bubble.

**5. User sends first message**

```http
POST /chat
Authorization: Bearer eyJhbGc...
{ "session_id": "550e8400-e29b-41d4-a716-446655440000", "message": "How do I say 'thank you'?" }
```
→ `200`

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "response": "In Japanese, 'thank you' is ありがとう (arigatou). A more formal version is ありがとうございます (arigatou gozaimasu).",
  "language": "Japanese"
}
```

The session title is now auto-set to `"How do I say 'thank you'?"`. Update the sidebar label.

**6. User sends another message**

```http
POST /chat
Authorization: Bearer eyJhbGc...
{ "session_id": "550e8400-e29b-41d4-a716-446655440000", "message": "What about 'please'?" }
```
→ `200` — display Lexie's reply. The title does not change (it was already set on the first message).

---

### Returning user — page reload, resume past session

**7. On page load, validate the stored token**

```http
GET /auth/me
Authorization: Bearer eyJhbGc...
```
→ `200` — token is still valid, proceed.
→ `401` — attempt refresh via `POST /auth/refresh`. If that also fails, redirect to login.

**8. Load session list for the sidebar**

```http
GET /sessions
Authorization: Bearer eyJhbGc...
```
→ `200`

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "language": "Japanese",
    "title": "How do I say 'thank you'?",
    "created_at": "2026-05-30T09:05:00",
    "updated_at": "2026-05-30T09:08:00"
  }
]
```

**9. User clicks the session in the sidebar**

Fetch the full history:

```http
GET /sessions/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer eyJhbGc...
```
→ `200` — render `messages` to populate the chat view.

Re-initialise the bot so Lexie can continue:

```http
POST /start-session
Authorization: Bearer eyJhbGc...
{ "session_id": "550e8400-e29b-41d4-a716-446655440000", "target_language": "Japanese" }
```
→ `200` — discard the greeting, the chat view is already showing the real history.

**10. User continues chatting** — repeat Step 5–6.

**11. User deletes the session**

```http
DELETE /sessions/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer eyJhbGc...
```
→ `204` — remove from sidebar, clear the chat view.

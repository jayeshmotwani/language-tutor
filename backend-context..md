# Backend Auth Integration — Context for Frontend Changes

## What was built on the backend

The FastAPI backend ("Lexie") now has a complete JWT Bearer token 
authentication system. Here is what changed:

### New auth endpoints

| Method | Path | Auth required | Description |
|--------|------|---------------|-------------|
| `POST` | `/auth/register` | No | Register a new user |
| `POST` | `/auth/login` | No | Login, returns access + refresh token |
| `POST` | `/auth/refresh` | No | Exchange refresh token for new access token |
| `GET`  | `/auth/me` | Bearer | Returns current authenticated user |

### Existing endpoints — now protected

| Method | Path | Auth required |
|--------|------|---------------|
| `GET`  | `/health` | No (still public) |
| `POST` | `/start-session` | **Bearer token required** |
| `POST` | `/chat` | **Bearer token required** |

These two endpoints now return `401 Unauthorized` if no token 
(or an invalid/expired token) is sent.

---

## Request and response shapes

### POST `/auth/register`
```json
// Request body
{
  "name": "Alex",
  "email": "alex@example.com",
  "password": "mypassword"   // min 8 characters
}

// Response — 201 Created
{
  "id": 1,
  "name": "Alex",
  "email": "alex@example.com",
  "is_active": true,
  "created_at": "2026-05-28T10:00:00"
}
POST /auth/login
// Request body
{
  "email": "alex@example.com",
  "password": "mypassword"
}

// Response — 200 OK
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer"
}
POST /auth/refresh
// Request body
{
  "refresh_token": "<jwt>"
}

// Response — 200 OK
{
  "access_token": "<new_jwt>",
  "token_type": "bearer"
}
GET /auth/me
// Header: Authorization: Bearer <access_token>

// Response — 200 OK
{
  "id": 1,
  "name": "Alex",
  "email": "alex@example.com",
  "is_active": true,
  "created_at": "2026-05-28T10:00:00"
}
POST /start-session (unchanged body, now needs token)
// Header: Authorization: Bearer <access_token>

// Request body — unchanged
{
  "session_id": "uuid-here",
  "target_language": "Japanese",
  "user_name": "Alex"         // optional
}
POST /chat (unchanged body, now needs token)
// Header: Authorization: Bearer <access_token>

// Request body — unchanged
{
  "session_id": "uuid-here",
  "message": "How do I say hello?"
}
Token strategy
Access token — short-lived (30 minutes). Attach to every
protected API call via Authorization: Bearer <token> header.
Refresh token — long-lived (7 days). Used only to get a new
access token when the current one expires. Never send this on
regular API calls.
Both tokens are plain JWTs signed with HS256.
What the frontend needs to change
1. Token storage
After a successful login, store both tokens:

localStorage.setItem('access_token', data.access_token);
localStorage.setItem('refresh_token', data.refresh_token);
On logout, clear them:

localStorage.removeItem('access_token');
localStorage.removeItem('refresh_token');
2. Attach token to every API call
Every request to /start-session and /chat (and /auth/me)
must include the header:

Authorization: Bearer <access_token>
3. Handle token expiry — silent refresh
When any API call returns 401, the frontend should:

Try POST /auth/refresh with the stored refresh token
Store the new access token
Retry the original failed request once
If the refresh also fails (refresh token expired),
redirect the user to the login page
4. New screens/flows needed
Register screen — form with name, email, password fields;
calls POST /auth/register, then redirects to login
Login screen — form with email, password; calls
POST /auth/login, stores tokens, redirects to chat
Protected route guard — wrap the chat UI in a route guard
that checks for a stored access token; redirect to login if missing
Logout button — clears stored tokens, redirects to login
5. Error handling
HTTP status	Meaning	Frontend action
400	Duplicate email on register	Show "Email already registered"
401	Invalid / expired token	Attempt refresh; if that fails, redirect to login
401	Wrong email or password on login	Show "Incorrect email or password"
422	Validation error (e.g. password too short)	Show field-level error
Backend base URL
http://localhost:8000
CORS is already configured to allow requests from:

http://localhost:3000
http://localhost:5173
The Authorization header is explicitly allowed by the backend's
CORS config, so no changes needed there.

Recommended axios setup
// src/api/axios.js
import axios from 'axios';

const api = axios.create({ baseURL: 'http://localhost:8000' });

// Attach access token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401 — try a silent token refresh, then retry once
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refresh = localStorage.getItem('refresh_token');
        const { data } = await axios.post(
          'http://localhost:8000/auth/refresh',
          { refresh_token: refresh }
        );
        localStorage.setItem('access_token', data.access_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch {
        localStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
Use this api instance for all calls instead of plain axios.
# Architecture & Design

## Overview

```
Client ── HTTP/JSON ──► FastAPI app ──┬── SQLAlchemy ──► PostgreSQL (Supabase)
                                      └── openai SDK ──► OpenRouter (DeepSeek v4 flash)
```

A classic layered API: FastAPI routers → service helpers → SQLAlchemy models.
Stateless JWT auth; every request carries the user's identity and all data
access is filtered by it.

## Data model

- **User** — email (unique), bcrypt-hashed password, optional display
  `name`, `preferences` JSON blob (e.g. `default_model`, `context_window`)
- **Project** — owned by a user (`user_id` FK). Fields: name, description,
  system_prompt, model. One project = one AI agent. Default model
  precedence: request → user's `default_model` preference → global default.
- **Conversation** — belongs to a project (`project_id` FK), `pinned` flag
  (pinned sorts first in the list)
- **Message** — belongs to a conversation (`conversation_id` FK), role
  (`user`/`assistant`/`tool`) + content + tool-call metadata
- **UsageEvent** — one row per model response (`user_id`, optional
  project/conversation FKs, model, prompt/completion/total tokens). Feeds
  the settings-page token meter and the optional daily cap.

All FKs cascade on delete; all ids are UUIDs (unguessable — prevents IDOR
enumeration on top of the ownership checks).

## Security model

1. **Ownership isolation (the core rule).** Every query for
   projects/conversations/messages joins or filters on the authenticated
   user's id (`app/services.py`). Non-owned resources return 404 — existence
   is never leaked.
2. **Credentials.** bcrypt (cost 12) at rest, never logged. JWT HS256 signed
   with a secret from env, `sub` = user UUID, `exp`/`iat` claims.
3. **Boundary validation.** Pydantic validates all input at the API edge;
   internal code trusts its types.
4. **Uniform errors.** Global handlers map everything to
   `{"error": "..."}` with correct status codes — no stack traces leak.

## Chat flow (the one endpoint that matters)

```
POST /projects/{pid}/conversations/{cid}/chat  {"message": "..."}
  1. Verify user owns project + conversation (404 otherwise)
  2. Load history (last 50 messages, ordered)
  3. Persist the user message (committed BEFORE the LLM call)
  4. Build prompt: system prompt (from project) + history + new message
  5. Call OpenRouter via openai SDK (chat.completions)
  6. Persist assistant reply, return it
  On LLM failure → 502 {"error": ...}; the user message is kept so the
  user can retry without losing context.
```

## Why these choices

- **Usage metering is record-only by default.** `usage_events` captures
  tokens after every model response; `GET /auth/me/usage` aggregates a
  rolling window (`usage_window_hours`, default 24). The chat endpoint only
  hard-blocks (`429`) when `usage_daily_token_limit` is set above 0 — the
  knob exists but is off by default, so metering never breaks a demo.
  Recording is best-effort (a failure must never take down a chat request).
- **JWT, not OAuth2.** OAuth2 is an authorization framework for third-party
  apps. For a first-party email/password API it adds a provider + redirect
  dance with no security benefit. Security comes from bcrypt, short-lived
  signed tokens, and ownership scoping.
- **OpenRouter over direct OpenAI.** The assignment brief explicitly allows
  any LLM service; OpenRouter gives DeepSeek v4 flash via an OpenAI-compatible
  API, so the official `openai` SDK works with a different `base_url`. Using
  `chat.completions` (the universally supported format) rather than the
  Responses API keeps the integration swappable.
- **SQLAlchemy generic `Uuid` type.** Renders as native UUID on Postgres and
  CHAR(32) on SQLite — tests run on in-memory SQLite; production is Postgres.
  No dialect coupling.
- **LLM client as a dependency.** `get_llm_client()` is injected into the
  chat route, so tests substitute a fake (records the exact prompt) — the
  LLM boundary is testable without network or cost.
- **User message persisted before the LLM call.** A failed generation doesn't
  destroy the user's turn; retrying resumes with full context.

## Extensibility (where the next features plug in)

- **RAG / file upload — SHIPPED (Part A, Step 6).** `project_files` +
  `file_chunks` tables, chunk size 1000 / overlap 150, nomic-embed-text-v1.5
  (local, loaded once) with `search_document:`/`search_query:` task
  prefixes, vectors in Postgres (pgvector), files in Supabase Storage
  (`project-files`). `search_chunks()` returns the top-K nearest chunks via
  `l2_distance`. **Known limit:** retrieval returns nearest matches without a
  relevance cutoff — a production version would add a distance threshold to
  avoid injecting irrelevant context.
- **Roles (RBAC)** — additive: a `role` column on users + a
  `require_admin` dependency. Explicitly out of scope for now.
- **Streaming** — the LLM boundary is a single `complete()` method;
  swapping to an SSE endpoint touches only the route, not the model layer.
- **Pagination** — list endpoints currently return full sets; add
  `limit/offset` as additive query params without breaking consumers.
- **Observability** — add middleware for request logging / metrics without
  changing routes.

## Settings slice (Step 6) — SHIPPED

- `PATCH /auth/me` — update profile name
- `GET`/`PATCH /auth/me/preferences` — read/write `default_model`,
  `context_window` (PATCH merges into the JSON blob)
- `DELETE /auth/me/conversations` — clear all of a user's conversations
  (projects + files survive), returns `{"deleted": n}`
- `DELETE /auth/me` — delete account; cascades projects/conversations/
  messages/usage, removes file blobs from storage best-effort
- `GET /auth/me/usage?window_hours=24` — per-user token aggregate
- `PATCH`/`DELETE /projects/{pid}/conversations/{cid}` — rename, pin, delete
  a thread; list is sorted pinned-first

## Known limits (accepted for scope)

- No migration tooling (Alembic) — additive schema changes ship via
  idempotent scripts in `scripts/` (`init_db.py`, `migrate_settings.py`);
  each runs `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` and
  `CREATE TABLE IF NOT EXISTS`, so they're safe to re-run against live
  Supabase. Tests stay unaffected (drop_all/create_all).
- No rate limiting / refresh tokens — out of scope for the assignment. A
  gentle token floor exists via `usage_daily_token_limit` but is off by
  default.
- Chat history window is fixed at the last 50 messages.

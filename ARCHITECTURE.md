# Architecture & Design

This document explains **how openagent is built and why**, covering the data
model, security model, the LLM + streaming layer, the RAG pipeline, the
tool-calling loop, usage metering, the frontend architecture, and the
deployment topology.

---

## 1. System overview

```
                    ┌──────────────────────────────────────────────────┐
                    │                    FastAPI app                   │
                    │                                                  │
   Browser  ────►   │  routers/auth ─┐                                  │
   (React)         │  routers/projects ─┤                              │
    │              │  routers/conversations ──► services ──► SQLAlchemy ──► PostgreSQL (Supabase)
    │   SSE        │  routers/files ──┘            │                    │
    │  (chat)      │                              │                    │  pgvector
    │              │       llm.py (LLMClient)     │                    │  (file_chunks)
    │              │          │                   │                    │
    │              │   ┌──────┴───────┐           │                    │
    │              │   │ opencode API │  primary │  (OpenAI-compatible │
    │              │   │  /zen/go/v1  │◄────────│   chat.completions) │
    │              │   └──────┬───────┘          │                    │
    │              │          │ fallback         │                    │
    │              │   ┌──────┴───────┐           │                    │
    │              │   │ Zen free mdl │  retry   │                    │
    │              │   └──────────────┘          │                    │
    │              │   tools: calculator (local),│                    │
    │              │          search_project_files (pgvector),        │
    │              │          web_search (Tavily) │                   │
    └──────────────┴──────────────────────────────────────────────────┘
```

A classic layered API — FastAPI routers → service helpers → SQLAlchemy
models — with two deliberately isolated boundaries:

1. **The LLM boundary** (`llm.py`): the only module that knows how to talk to
   a model. Everything else consumes a small event stream.
2. **The embedding/storage boundary** (`embeddings.py`, `storage.py`): local
   models and object storage behind interfaces that can be swapped.

Stateless JWT auth; every request carries the user's identity and **all** data
access is filtered by it.

---

## 2. Data model

| Table | Purpose | Key columns |
|---|---|---|
| `users` | Account | `email` (unique), `hashed_password` (bcrypt), `name`, `preferences` (JSON) |
| `projects` | One chatbot per project | `user_id` FK, `name`, `description`, `system_prompt`, `model` |
| `conversations` | A thread inside a project | `project_id` FK, `title`, `pinned` (pinned sorts first) |
| `messages` | Chat messages | `conversation_id` FK, `role` (`user`/`assistant`/`tool`), `content`, `reasoning`, `tool_call_id`, `tool_name`, `tool_arguments` |
| `project_files` | Uploaded documents | `project_id` FK, `user_id`, `original_filename`, `mime_type`, `size_bytes`, `storage_path`, `chunk_count` |
| `file_chunks` | Embedded document segments | `file_id` FK, `project_id`, `chunk_index`, `content`, `embedding` (vector(768)) |
| `usage_events` | Metering (one row per model response) | `user_id`/`project_id`/`conversation_id` FKs, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens` |

- All FKs cascade on delete; all ids are **UUIDs** (unguessable — prevents
  IDOR enumeration on top of the ownership checks).
- **Model precedence:** explicit request → project's `model` → user's
  `preferences.default_model` → global `DEFAULT_MODEL`.
- The `embedding` column uses the `vector(768)` type from **pgvector**.
  Retrieval orders by `embedding <-> query` (L2 distance). The demo relies on
  sequential scans (document counts are small); a production version would add
  an HNSW/IVFFlat index for large corpora.

---

## 3. Security model

1. **Ownership isolation (the core rule).** Every query for
   projects/conversations/messages/files joins or filters on the authenticated
   user's id (`app/services.py`). Non-owned resources return **404** —
   existence is never leaked.
2. **Credentials.** bcrypt (cost 12) at rest, never logged. JWT HS256 signed
   with a secret from env; `sub` = user UUID, `exp`/`iat` claims, 24h
   lifetime. No refresh tokens — on 401 the frontend signs the user out.
3. **Boundary validation.** Pydantic validates all input at the API edge;
   internal code trusts its types.
4. **Safe tool execution.** The calculator evaluates arithmetic through
   Python's `ast` module with an allow-list of operators and a max-exponent
   guard — **never `eval`**, no code injection. Web search uses stdlib
   `urllib` over HTTPS only.
5. **Uniform errors.** Global handlers map everything to `{"error": "..."}`
   with correct status codes — no stack traces leak.
6. **Secret hygiene.** Keys come exclusively from env vars (`.env` /
   Railway). `.env`, `MEMORY.md`, `PROGRESS.md`, `CONTEXT.md` are gitignored,
   and internal notes were purged from git history before going public.

---

## 4. The LLM layer

### 4.1 Provider abstraction

`app/llm.py` wraps the official **`openai` SDK** pointed at any
OpenAI-compatible `chat.completions` endpoint. The provider is chosen entirely
by env vars:

- **Primary:** the **opencode API** (`https://opencode.ai/zen/go/v1`) — one
  OpenAI-compatible endpoint that fronts a large catalog of models (DeepSeek
  V4 Flash/Pro, MiniMax, Kimi, GLM, Qwen, Mimo, Grok, GPT-5.6 Luna, HY3).
  Default model: `deepseek-v4-flash`.
- **Fallback:** **OpenCode Zen free models** (`https://opencode.ai/zen/v1`),
  default fallback model `deepseek-v4-flash-free` — the demo keeps working
  for free when the primary is down/rate-limited. When
  `OPENAI_FALLBACK_API_KEY` is empty the primary key is reused; a separate
  provider (e.g. OpenRouter) can be configured instead via the `OPENAI_FALLBACK_*`
  vars.

This is exactly the "OpenRouter Completion API / any LLM service of choice"
option from the assignment brief — implemented without locking the app to a
single vendor.

### 4.2 Automatic provider fallback

`LLMClient.stream()` builds an attempt list of `(client, model, label)`:
primary first, then fallback. When the primary raises a **retryable** error —
`RateLimitError`, `APIConnectionError`, `APITimeoutError`,
`InternalServerError`, or any status ≥ 500 — *before yielding its first
delta*, the whole pass is retried on the fallback provider with the fallback
model id. Non-retryable errors (4xx: bad model, auth) propagate immediately —
they would fail identically on any provider.

Mid-stream failures are **not** retried (the user has already rendered text
from the failing provider). The chosen provider is announced via an SSE
`provider` event before any tokens stream, so the UI can badge fallback
responses live (`fallback · <model>`).

### 4.3 Streaming event protocol

`LLMClient.stream()` yields a uniform iterator of events, decoupling the route
from provider quirks:

| Event | Payload | Source |
|---|---|---|
| `provider` | `{provider, model}` | emitted before the first delta |
| `thinking` | `{text}` | `delta.reasoning_content` / `delta.reasoning` |
| `content` | `{text}` | `delta.content` |
| `tool` | `{id, name, arguments}` | accumulated `delta.tool_calls` |
| `result` | `{content, reasoning, tool_calls, usage, provider, model}` | end of pass |

### 4.4 Reasoning effort

The per-message `Standard` / `Max` toggle maps to the provider's reasoning
parameter:

- `standard` → the parameter is **omitted entirely** (fast, cheap).
- `max` → `extra_body={"reasoning": {"effort": "xhigh"}}` (deep reasoning).

Implemented through the SDK's `extra_body` mechanism (required for
openai SDK 1.109.x) and covered by tests.

---

## 5. The chat flow (SSE)

```
POST /projects/{pid}/conversations/{cid}/chat
  1. Verify the user owns project + conversation (404 otherwise)
  2. Enforce usage caps → 429 if any rolling window is exhausted
  3. Load history (last 50 messages, replayed with tool_calls/tool results)
  4. Persist the user message (committed BEFORE the LLM call)
  5. Build the prompt: project system_prompt + artifact_guidance + history
  6. Run the tool-calling loop (see §6) against the LLM client
  7. Meter the response (usage_events), re-enforce caps
  8. Persist the assistant reply + reasoning + tool calls/results
  9. Return a StreamingResponse (text/event-stream)
```

Notes:

- **The user message is persisted before the LLM call.** A failed generation
  never destroys the user's turn; retrying resumes with full context.
- **History replay** (`build_chat_messages`) reconstructs the exact OpenAI
  message list from persisted rows — assistant tool-call turns carry their
  `tool_calls` array, each `role=tool` result is linked by `tool_call_id`.
- **Attachments** are injected inline as message context (`--- File: X ---`
  blocks), *not* embedded — that's the one-off path; persistent knowledge goes
  through RAG (§7).

---

## 6. The tool-calling loop

The chat route runs an **agentic loop** (max `MAX_TOOL_TURNS = 4`):

```
for round in 0..MAX_TOOL_TURNS:
    stream = llm.stream(model, messages, tools=available_tools(), reasoning_effort)
    if result has no tool_calls:
        → persist assistant message, stream done event, return
    else:
        → persist the assistant tool-call turn
        → append assistant(tool_calls) to messages
        → for each tool call:
              args = json.loads(arguments)
              result_text = execute_tool(name, args, db, project_id, embedder)
              → persist as role=tool message (linked by tool_call_id)
              → append tool(result) to messages
        → loop (the model now sees tool outputs)
```

### The tools

| Tool | Implementation | Safety |
|---|---|---|
| `calculator` | `ast`-based safe arithmetic evaluation | allow-listed ops, no `eval`, exponent guard |
| `search_project_files` | embeds the query, returns top-4 chunks by L2 distance | scoped to `project_id` only |
| `web_search` | Tavily API POST (stdlib `urllib`) | **only offered when `TAVILY_API_KEY` is set**; failures return `"Error: web search unavailable"` so the loop recovers |

Design rules:

- **Never offered-then-failed.** `available_tools()` filters `web_search` out
  entirely when its key is unset — the model can't pick a tool that will fail.
- **Tool errors are data, not exceptions.** A failing tool returns an
  `"Error: ..."` string to the model, which can recover mid-loop. Only an
  unknown tool name raises.
- Every tool call and its result is **persisted** as part of the conversation,
  so history replay is faithful and reload-safe.
- If the model never finishes within the turn budget, the endpoint returns a
  clean error event instead of hanging.

---

## 7. Embeddings & RAG

### 7.1 Why local embeddings (not the OpenAI Files API)

The brief suggested the OpenAI Files API as "good to have". openagent instead
runs a **self-contained pipeline** — and that's deliberate:

- **No per-file API cost / no OpenAI credits required** — embeddings run
  locally and offline.
- **Files stay in our own storage** (Supabase Storage), not a third party's.
- **Full control** over chunking, prefixes, and retrieval — no black box.
- **Provider-agnostic** — RAG works regardless of which model answers.

### 7.2 The embedding model

- **nomic-embed-text-v1.5**, 768-dim, loaded **once** as a module-level
  singleton (`embeddings.py`) — never per-request.
- Downloaded into the HF cache **at Docker build time**; at runtime the module
  makes **no network calls** — the demo works offline.
- **Preloaded at app startup** (FastAPI lifespan) — first lazy load would cost
  ~2.5 min and make a fresh container's first request look broken.
- **Task prefixes are required** for retrieval quality with this model:
  document chunks get `search_document: `, queries get `search_query: `.

### 7.3 The upload pipeline

```
POST /projects/{pid}/files
  1. Ownership check (404 if not yours)
  2. Read + size-cap at 10 MB
  3. extract_text() — pypdf for PDF, python-docx for DOCX, UTF-8 otherwise
     (allowed: txt/md/csv/json/log + code extensions, pdf, docx)
  4. chunk_text() — 1000 chars, 150 overlap (context continuity at boundaries)
  5. embed_chunks() — DOCUMENT_PREFIX + chunk → local model → vector
  6. Persist ProjectFile row + FileChunk rows (vector(768)) + blob in storage
     → single commit (all-or-nothing)
```

### 7.4 Retrieval at chat time

When the model calls `search_project_files`:

```
query_vector = embed_query("search_query: " + query)      # same model
rows = SELECT content FROM file_chunks
       WHERE project_id = :pid
       ORDER BY embedding <-> :query_vector               # L2 distance
       LIMIT 4
```

The top-4 chunks are returned to the model as tool output, and the model
grounds its answer in them — **retrieval-augmented generation**. Retrieval is
scoped strictly by `project_id`, so one project's documents never leak into
another project's answers.

> **Known limit:** retrieval returns nearest matches without a relevance
> cutoff. A production version would add a distance threshold to avoid
> injecting irrelevant context.

---

## 8. Usage metering & limits (Part B)

### 8.1 Recording

Every model response writes one `usage_events` row (prompt/completion/total
tokens + model + FKs). Recording is **best-effort** — a metering failure must
never take down a chat request.

### 8.2 Enforcement

`_enforce_usage_limit()` checks each configured **rolling window** and returns
`429 {"error": "Session token usage limit reached..."}` as soon as any window
is exhausted. A limit `<= 0` disables that window.

| Window | Default (config) | Live demo (Railway env) |
|---|---|---|
| Session | 50k tokens / 5h | **200k tokens / 5h** |
| Weekly | 500k tokens / 7d | **2M tokens / 7d** |
| Daily | 0 (disabled) | disabled |

Rolling windows **never reset on a schedule** — the countdown
(`seconds_until_reset`) is the time until the oldest counted event ages out,
so the bar percentage decays continuously as tokens expire.

The composer renders live `Session` / `Weekly` bars from
`GET /auth/me/usage`. These caps are **self-imposed demo limits (UX
guardrails)**, not provider billing quotas — but the enforcement machinery is
exactly what would ship against real billing tiers.

---

## 9. Frontend architecture

`frontend/` — React 18 + TypeScript + Vite + Tailwind + React Router.

### 9.1 Performance

- **Route-level code splitting** (`React.lazy`) — the entry bundle is ~56 kB
  gzipped; the heavy Workspace chunk (~56 kB gzipped) loads only when a
  project is opened.
- **Memoized chat rendering** — `ChatMessage` is wrapped in `memo` with a
  field-level equality check (id/role/content/created_at/reasoning/tool data),
  so only the changed row re-renders.
- **Buffered SSE flushing** — streaming deltas accumulate in refs and are
  flushed into a single `setDraft` on a 40 ms interval (within the 30–50 ms
  spec), then flushed on stream end and on unmount. No per-token re-render
  storms.

### 9.2 The streaming experience

- `thinking` deltas feed the **live chain-of-thought block**, which is
  **expanded by default during streaming** (so the user watches the model
  reason in real time) and collapses after completion; the full reasoning is
  persisted and expandable on reload.
- `content` deltas render through `react-markdown` (headings, lists, tables,
  fenced code blocks).
- Tool calls render as inline tool cards with live argument streaming.
- `provider` events switch the header badge to `fallback · <model>` live.
- Fenced code blocks open in a **Canvas** pane — full-screen, syntax-colored,
  no chat noise.

### 9.3 Responsive / mobile-first

- `< 640px`: usage strip + breadcrumbs hide, project toolbar wraps, composer
  stays fully usable with the reasoning toggle.
- Sidebar becomes a slide-in **drawer** (close button + tap-outside overlay);
  the header gains a back arrow on mobile.
- Desktop sidebar (> 1024px) is visible by default; the collapse toggle is in
  the header.

### 9.4 State & data flow

- `AuthContext` holds the JWT + user; `aw_token` / `aw_user` in localStorage.
- A global `aw:unauthorized` event (fired on any 401) signs the user out.
- The workspace owns one `streamChat` loop per send, managing the SSE reader
  and the buffered flush.

---

## 10. Deployment topology

```
                    ┌──────────────────────────────┐
   openagent.up.railway.app  ──►  Railway service  │
        (proxy)              │  agent-platform-api  │
                    │  multi-stage Docker image     │
                    │  ├─ uvicorn :8000 (FastAPI)   │
                    │  │   serves frontend/dist     │
                    │  └─ preloaded embedder         │
                    └──────────────┬───────────────┘
                                   │
        ┌──────────────────────────┼───────────────────┐
        ▼                          ▼                   ▼
   Supabase Postgres         Supabase Storage      opencode API
   (pooler, sslmode=require) (project-files bucket) (primary LLM)
                                            OpenRouter (fallback LLM)
                                            Tavily (web_search)
```

- **Multi-stage Dockerfile** — Node builds the frontend; Python installs
  CPU-only torch first, then requirements, then snapshots the embedding model
  into the HF cache. The final image serves API + SPA on one port.
- **Railway** listens on the injected `PORT`, auto-deploys on every push to
  `main`, and routes the public domain `openagent.up.railway.app`.
- **Supabase** provides Postgres (via the IPv4 pooler URL with
  `sslmode=require`) and object storage for file blobs.
- **Provider resilience** — primary = opencode API, fallback = OpenRouter, so
  the demo keeps working through provider outages.

---

## 11. Why these choices (design rationale)

- **OpenAI-compatible `chat.completions` over the Responses API.** The brief
  explicitly allows any LLM service. `chat.completions` is the universally
  supported format — the official `openai` SDK works against opencode /
  OpenRouter / any vendor with a different `base_url`, keeping the integration
  swappable with zero code changes.
- **Custom file/RAG pipeline over the OpenAI Files API.** Free, offline,
  provider-agnostic, and fully controllable — see §7.1.
- **JWT, not OAuth2.** OAuth2 is an authorization framework for third-party
  apps; for a first-party email/password API it adds a provider + redirect
  dance with no security benefit. Security comes from bcrypt, signed
  short-lived tokens, and ownership scoping.
- **SSE over WebSocket.** SSE is one-directional, automatic-reconnecting, and
  rides plain HTTP — sufficient for streaming model output and much simpler to
  proxy, test, and operate.
- **pgvector over a separate vector DB.** Chunks live next to the data they
  belong to (same Postgres, transactional uploads), no extra service to run.
- **Local embedding model over a hosted embedding API.** The demo must work
  offline and cheaply; the model is small (768-dim) and fast on CPU.
- **LLM client as an injected dependency.** Tests substitute a fake that
  records the exact prompt — the LLM boundary is testable without network or
  cost.
- **User message persisted before the LLM call.** A failed generation doesn't
  destroy the user's turn; retry resumes with full context.
- **UUID ids everywhere.** Unguessable identifiers defeat IDOR enumeration on
  top of the ownership checks.
- **SQLAlchemy generic `Uuid` type.** Native UUID on Postgres, CHAR(32) on
  SQLite — tests run on in-memory SQLite, production is Postgres, no dialect
  coupling.

---

## 12. Known limits (accepted for scope)

- **No migration tooling (Alembic).** Additive schema changes ship via
  idempotent scripts (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT
  EXISTS`) safe to re-run against live Supabase.
- **No rate limiting / refresh tokens** — out of scope for the assignment.
  A token floor exists via the usage windows (§8) but is not a request
  rate limiter.
- **Chat history window is fixed** at the last 50 messages.
- **RAG has no relevance cutoff** — retrieval returns the nearest chunks even
  when nothing is a close match (see §7.4).
- **No observability dashboards** — out of scope; the app logs to stdout.

---

## 13. Tests

119 tests across `tests/`, run with `pytest` (no network, no real LLM):

- **Auth** — register/login/me/preferences/usage, password hashing, token
  expiry.
- **Projects** — CRUD, per-user isolation (cross-user access → 404).
- **Conversations** — create, rename, pin, delete, per-project scoping.
- **Chat** — prompt construction, history replay, SSE event sequencing,
  reasoning-effort routing, fallback behavior.
- **Tools** — calculator correctness/safety, RAG retrieval, web-search gating.
- **Files/RAG** — upload, extraction, chunking, embedding, retrieval.
- **Usage** — metering, window aggregation, 429 enforcement.

The LLM and storage boundaries are injected dependencies, so the whole suite
runs against a fake LLM and fake storage — fast, deterministic, and free.

# openagent — Multi-Tenant Chatbot Platform

A production-shaped, multi-tenant chatbot platform. Users register, create
**projects** (each project is one chatbot with its own system prompt and
model choice), and chat with an LLM through a live-streaming chat interface
with chain-of-thought reasoning, tool use, document-based answers (RAG), and
enforced usage limits.

Built as a take-home assignment for yellow.ai (SDE-1) — but engineered like a
real product: real auth, real persistence, resilient LLM routing, a test suite
of 119 tests, and a live public deployment.

- **Live demo:** https://openagent.up.railway.app
- **Repo:** https://github.com/ShivamChavan01/agent-platform

---

## Features

### Core chat experience
- **Live streaming over Server-Sent Events** — the model's reply streams in
  token-by-token, no spinner, no waiting for full generation.
- **Live chain-of-thought** — the model's reasoning streams in *before* the
  answer and is shown **expanded in real time** while generating, then
  collapses after completion (click to expand anytime). Persisted with the
  message, so it survives a page reload.
- **Reasoning-effort control** — per-message `Standard` / `Max` toggle. `Max`
  sends `reasoning_effort: xhigh` to the provider for deeper reasoning.
- **Full markdown rendering** — headings, lists, bold, tables, code blocks
  with syntax highlighting.

### Multi-model support
- **Any model under the opencode API** — DeepSeek V4 Flash (default) / V4 Pro,
  MiniMax M3/M2.7/M2.5, Kimi K3/K2.7/K2.5, GLM 5.2/5.1/5, Qwen 3.8/3.7/3.6/3.5,
  Mimo V2 Omni/2.5 Pro/2.5, HY3, GPT-5.6 Luna, Grok 4.5 — all through one
  OpenAI-compatible interface, selectable per project **and mid-conversation**.
- **Automatic provider fallback** — if the primary provider fails before the
  first token (rate limit, connection error, 5xx), the same request is retried
  on a secondary provider (OpenRouter). The UI badges fallback responses live.

### Agentic tool use
- **Tool-calling loop** (up to 4 rounds per message) — the model decides which
  tools it needs and iterates:
  - **`calculator`** — safe arithmetic evaluation via Python's `ast` module
    (never `eval`, no code injection).
  - **`search_project_files`** — vector retrieval over the project's uploaded
    documents (see RAG below).
  - **`web_search`** — real-time web search via the Tavily API. Only offered
    to the model when `TAVILY_API_KEY` is set (never offered-then-failed).

### Document answers (RAG)
- **Upload files to a project** — plain text formats (txt/md/csv/json/code)
  plus PDF and DOCX, up to 10 MB each.
- **Local embedding pipeline** — files are extracted, chunked (1000 chars,
  150 overlap), embedded with **nomic-embed-text-v1.5** (768-dim, runs fully
  locally) and stored as pgvector vectors in Postgres.
- **Retrieval-augmented generation** — at chat time the model searches the
  project's top-4 nearest chunks (L2 distance) and grounds its answer in the
  actual document text. Scoped per project — files never leak across projects.
- **Message attachments** — files can also be attached directly to a message
  and injected inline as context (not embedded), for one-off questions.

### Code canvas
- Fenced code blocks open in a **full-screen Canvas** view — clean monospace,
  syntax colors, no chat noise.

### Usage limits (Part B)
- **Server-side metering** — every model response is recorded in a
  `usage_events` table; counts survive restarts.
- **Rolling budget windows** — Session (default 200k tokens / 5h) and Weekly
  (default 2M tokens / 7d), shown as live bars in the composer. Exceeding a
  cap returns **HTTP 429** with a friendly message. Caps are config-driven.

### Account management
- JWT auth with bcrypt password hashing; 24h token lifetime.
- Settings: profile, per-user preferences (default model, context window),
  clear all conversations, delete account, usage overview.
- Fully responsive **mobile-first** UI — drawer navigation, adaptive layouts.

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, **FastAPI** (async, SSE streaming) |
| ORM | **SQLAlchemy 2.0** |
| Database | **PostgreSQL** (Supabase), pgvector for embeddings |
| Auth | **JWT** (python-jose) + **bcrypt** password hashing (passlib) |
| LLM | official **`openai` SDK** → `chat.completions` against any OpenAI-compatible endpoint |
| Embeddings | **nomic-embed-text-v1.5** (local, 768-dim) via sentence-transformers |
| Storage | **Supabase Storage** (`project-files` bucket), local dir fallback |
| Web search | **Tavily API** (optional, gated) |
| Frontend | **React 18**, TypeScript, **Vite**, Tailwind CSS, React Router, react-markdown |
| Deployment | Multi-stage **Docker**, **Railway** (auto-deploy from `main`) |

---

## Quick start (local)

```bash
# 1. Python 3.11+ + PostgreSQL running locally
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Create the database (peer auth as your OS user)
createdb agent_platform

# 3. Configure secrets
cp .env.example .env
# edit .env:
#   OPENAI_API_KEY=<your opencode / OpenRouter key>
#   JWT_SECRET=<random string>
#   DATABASE_URL=postgresql+psycopg2:///agent_platform   (local) or your Supabase pooler URL

# 4. Create tables
python -m scripts.init_db

# 5. Run the backend
uvicorn app.main:app --reload

# 6. In a second terminal, run the frontend dev server
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api and SSE to :8000)
```

API docs (FastAPI): http://127.0.0.1:8000/docs

### Choosing an LLM provider

The chat endpoint talks to any OpenAI-compatible `chat.completions` server —
the provider is env-swappable with zero code changes.

- **opencode API** (default, many models, one key):
  ```env
  OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
  OPENAI_API_KEY=sk-...            # see ~/.local/share/opencode/auth.json
  DEFAULT_MODEL=deepseek-v4-flash  # full catalog: GET {BASE}/models
  ```
- **OpenRouter**:
  ```env
  OPENAI_BASE_URL=https://openrouter.ai/api/v1
  OPENAI_API_KEY=sk-or-v1-...
  DEFAULT_MODEL=deepseek/deepseek-v4-flash
  ```

### Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2:///agent_platform` | SQLAlchemy URL (unix-socket peer auth for local dev; Supabase pooler for prod) |
| `JWT_SECRET` | `change-me-in-prod` | HMAC secret for JWT signing — set a random value |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token lifetime (minutes) |
| `OPENAI_API_KEY` | (empty) | Primary provider key (opencode-go or OpenRouter, `sk-...`) |
| `OPENAI_BASE_URL` | `https://openrouter.ai/api/v1` | Primary LLM endpoint (OpenAI-compatible) |
| `DEFAULT_MODEL` | `deepseek/deepseek-v4-flash` | Model used when a project sets none |
| `OPENAI_FALLBACK_API_KEY` | (empty) | Secondary provider key — used when the primary fails before yielding tokens |
| `OPENAI_FALLBACK_BASE_URL` | `https://openrouter.ai/api/v1` | Fallback endpoint |
| `OPENAI_FALLBACK_MODEL` | `deepseek/deepseek-v4-flash` | Fallback model id (OpenRouter-prefixed when falling back from an unprefixed catalog) |
| `EMBEDDING_MODEL` | `nomic-ai/nomic-embed-text-v1.5` | Local embedding model (768-dim) |
| `EMBEDDING_DIM` | `768` | Vector dimension (must match the model) |
| `PRELOAD_EMBEDDER` | `true` | Preload the embedder at startup (first lazy load ≈ 2.5 min). Set `false` in tests |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | (empty) | Enable Supabase Storage (bucket `project-files`); empty → local `storage/` dir |
| `SUPABASE_STORAGE_BUCKET` | `project-files` | Storage bucket name |
| `MAX_UPLOAD_BYTES` | `10485760` | Upload size cap (10 MB) |
| `USAGE_WINDOW_HOURS` | `24` | Rolling window for the daily aggregate |
| `USAGE_DAILY_TOKEN_LIMIT` | `0` | Optional per-user 24h token cap (0 = disabled) |
| `SESSION_TOKEN_LIMIT` | `50000` | Session budget shown in the composer (0 = disabled) |
| `SESSION_TOKEN_WINDOW_HOURS` | `5` | Session window length |
| `WEEKLY_TOKEN_LIMIT` | `500000` | Weekly budget shown in the composer (0 = disabled) |
| `WEEKLY_TOKEN_WINDOW_HOURS` | `168` | Weekly window length (7 days) |
| `TAVILY_API_KEY` | (empty) | Enables the `web_search` tool when set |

> Deployment note: the live instance sets `SESSION_TOKEN_LIMIT=200000` and
> `WEEKLY_TOKEN_LIMIT=2000000` — the same caps shown in the demo.

---

## Deploy (Docker / Railway)

The Dockerfile is a multi-stage build:
1. Node stage builds the React frontend (`npm run build`).
2. Python stage installs **CPU-only torch first** from the PyPI CPU index (the
   default CUDA wheel is multi-GB and useless without a GPU), installs
   requirements, and **downloads the embedding model into the HF cache at
   build time** — so the runtime never makes network calls and the first
   request of a fresh container is fast.
3. The final image serves the API and the built frontend on the same port.

```bash
docker build -t agent-platform .
docker run --env-file .env -p 8000:8000 agent-platform
```

**Railway:** point a service at the repo root (Dockerfile is auto-detected),
set the env vars above, attach Supabase Postgres, then run the migrations:

```bash
python -m scripts.init_db            # fresh DB
python -m scripts.migrate_settings   # idempotent: users.name/preferences, pinned, usage_events
python -m scripts.migrate_reasoning  # idempotent: messages.reasoning
```

Every push to `main` triggers an automatic Railway deploy.

> **Heavy deps on a tight disk (local dev)?** The embedding stack
> (torch + sentence-transformers ≈ 1.5 GB + model cache ≈ 0.6 GB) can live on
> a separate partition with redirected caches, e.g.
> `HF_HOME=/opt/hf-cache PIP_CACHE_DIR=/opt/pip-cache`. Deployment platforms
> build their own environment anyway.

---

## API

All endpoints return JSON. Errors are always `{"error": "..."}` with a proper
HTTP status code. Authenticated endpoints require
`Authorization: Bearer <token>`.

### Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Register `{name?, email, password}` → `{access_token, user}` (auto-login) |
| `POST` | `/auth/login` | Login `{email, password}` → `{access_token, user}` |
| `GET` | `/auth/me` | Current user |
| `PATCH` | `/auth/me` | Update profile (`name`) |
| `GET` / `PATCH` | `/auth/me/preferences` | Read / merge-update `{default_model, context_window}` |
| `DELETE` | `/auth/me/conversations` | Delete all my conversations → `{"deleted": n}` |
| `DELETE` | `/auth/me` | Delete account (cascades all data, removes storage blobs) |
| `GET` | `/auth/me/usage?window_hours=24` | Token aggregate + `session` / `weekly` budget windows |

### Projects — each project is one chatbot

| Method | Path | Description |
|---|---|---|
| `POST` | `/projects` | Create `{name, description?, system_prompt?, model?}` |
| `GET` | `/projects` | List my projects |
| `GET` | `/projects/{id}` | Get one project (404 if not yours) |
| `PATCH` | `/projects/{id}` | Partial update (e.g. switch model) |
| `DELETE` | `/projects/{id}` | Delete |

### Conversations & chat

| Method | Path | Description |
|---|---|---|
| `POST` | `/projects/{pid}/conversations` | Create `{title?}` |
| `GET` | `/projects/{pid}/conversations` | List (pinned first) |
| `GET` | `/projects/{pid}/conversations/{cid}` | Conversation + messages |
| `PATCH` | `/projects/{pid}/conversations/{cid}` | Rename / pin / unpin |
| `DELETE` | `/projects/{pid}/conversations/{cid}` | Delete a conversation |
| `POST` | `/projects/{pid}/conversations/{cid}/chat` | Send `{message, reasoning_effort?, attachments?}` → **SSE stream** |

### Files (RAG source material)

| Method | Path | Description |
|---|---|---|
| `POST` | `/projects/{pid}/files` | Upload a file (multipart) — extracted, chunked, embedded |
| `GET` | `/projects/{pid}/files` | List the project's files |

### SSE chat event protocol

Each line is `data: <json>\n\n`:

| Event | Payload | Meaning |
|---|---|---|
| `provider` | `{provider, model}` | Which provider/model answered (badges fallback live) |
| `thinking` | `{delta}` | A live chain-of-thought chunk |
| `content` | `{delta}` | A live answer chunk |
| `tool` | `{id, name, arguments}` | A tool call in progress |
| `done` | `{message_id, content, reasoning, model, provider, usage}` | Generation complete |
| `error` | `{error}` | A failure (also used for 429 usage-cap rejection) |

**Every project/conversation/message query is scoped to the authenticated
user** — cross-user access returns 404 (existence is never leaked).

---

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

**119 tests** covering: auth (register/login/me/preferences/usage), project
CRUD + per-user isolation, conversations (rename/pin/delete), chat prompt
construction, SSE event streaming, LLM provider fallback, reasoning-effort
routing, tool calling (calculator / search_project_files), upload + RAG, and
usage metering. The LLM and storage boundaries are injected dependencies, so
tests run against a fake LLM + fake storage with **no network and no cost**.

---

## Project layout

```
app/
  main.py            FastAPI app, lifespan (embedder preload), error handlers
  config.py          env-driven settings (incl. fallback provider, usage caps)
  database.py        engine / session / Base
  models.py          User, Project, Conversation, Message, ProjectFile,
                     FileChunk, UsageEvent
  schemas.py         Pydantic request/response contracts
  security.py        bcrypt hashing + JWT create/decode
  dependencies.py    get_current_user (Bearer token)
  llm.py             LLM client — streaming, reasoning effort, provider fallback
  services.py        ownership helpers, usage aggregation
  embeddings.py      nomic-embed-text-v1.5 singleton (task-prefix aware)
  storage.py         Supabase Storage / local-dir boundary
  rag.py             text extraction, chunking, embedding, pgvector search
  tools.py           calculator + search_project_files + web_search (Tavily)
  routers/
    auth.py          register / login / me / preferences / usage
    projects.py      project CRUD
    conversations.py conversations + SSE chat + tool loop + usage enforcement
    files.py         upload / list
scripts/
  init_db.py           create tables
  migrate_settings.py  idempotent settings/usage migrations
  migrate_reasoning.py idempotent messages.reasoning migration
frontend/
  src/pages/         Login, Dashboard, Workspace, Settings
  src/components/    Composer, ChatMessage, StreamingMessage, ThinkingBlock,
                     CanvasPane, NavSidebar, Header, Logo, ...
tests/               pytest suite (fake LLM + fake storage, no network)
```

See `ARCHITECTURE.md` for the full design rationale.

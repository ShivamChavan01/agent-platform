# Agent Platform

A minimal multi-tenant chatbot platform. Users register, create "projects"
(each project is one AI agent with its own system prompt), and chat with their
agent through an LLM (OpenRouter / DeepSeek v4 flash).

Built as a take-home assignment — deliberately minimal: auth, projects,
conversations, chat with live-streamed reasoning, automatic provider
fallback, file upload + RAG, canvas preview, usage metering.

Live demo: https://openagent.up.railway.app (public repo, auto-deploys from `main`)

## Tech stack

- Python 3.11+, FastAPI (SSE streaming chat)
- SQLAlchemy 2.0 ORM
- PostgreSQL (local dev; Supabase-compatible — swap the URL)
- JWT auth (python-jose) + bcrypt password hashing (passlib)
- LLM via the official `openai` SDK pointed at any OpenAI-compatible
  `chat.completions` endpoint (OpenRouter / opencode-go), with automatic
  fallback to a secondary provider (rate limit / connection / 5xx)
- pgvector embeddings (nomic-embed-text-v1.5, dim 768) + Supabase Storage
- React + Vite frontend (`frontend/`, dev server proxies to :8000)

## Quick start

```bash
# 1. Python 3.11+ + PostgreSQL running locally
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Create the database (peer auth as your OS user)
createdb agent_platform

# 3. Configure secrets
cp .env.example .env
# edit .env: OPENAI_API_KEY=<provider key>
#            JWT_SECRET=<random string>
#
# LLM provider is env-swappable. The chat endpoint talks to any OpenAI-
# compatible `chat.completions` server:
#   - opencode-go (many models, single key): 
#       OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
#       OPENAI_API_KEY=sk-...   (see ~/.local/share/opencode/auth.json)
#       DEFAULT_MODEL=deepseek-v4-flash
#       # full catalog: GET {BASE}/models  (minimax-*, kimi-*, glm-*, qwen-*,
#       #                                  deepseek-v4-flash/pro, gpt-5.6-luna, ...)
#   - OpenRouter (original default):
#       OPENAI_BASE_URL=https://openrouter.ai/api/v1
#       OPENAI_API_KEY=sk-or-v1-...
#       DEFAULT_MODEL=deepseek/deepseek-v4-flash

# 4. Create tables
python -m scripts.init_db

# 5. Run
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2:///agent_platform` | SQLAlchemy URL (unix-socket peer auth for local dev) |
| `JWT_SECRET` | `change-me-in-prod` | HMAC secret for JWT signing — set a random value |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token lifetime |
| `OPENAI_API_KEY` | (empty) | Provider API key (OpenRouter or opencode-go, `sk-...`) |
| `OPENAI_BASE_URL` | `https://openrouter.ai/api/v1` | LLM endpoint (OpenAI-compatible) |
| `DEFAULT_MODEL` | `deepseek/deepseek-v4-flash` | Model when a project sets none |
| `OPENAI_FALLBACK_API_KEY` | (empty) | Secondary provider key — used when the primary fails (rate limit / 5xx) before yielding tokens |
| `OPENAI_FALLBACK_BASE_URL` | `https://openrouter.ai/api/v1` | Fallback endpoint |
| `OPENAI_FALLBACK_MODEL` | `deepseek/deepseek-v4-flash` | Fallback model id (OpenRouter-prefixed when falling back from an unprefixed catalog) |
| `PRELOAD_EMBEDDER` | `true` | Preload the embedding model at startup (first lazy load ≈ 2.5 min). Set `false` in tests |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | (empty) | Enable Supabase Storage (bucket `project-files`); empty → local `storage/` dir |
| `MAX_UPLOAD_BYTES` | `10485760` | Upload size cap (10 MB) |
| `USAGE_DAILY_TOKEN_LIMIT` | `0` | Optional per-user 24h token cap (0 = unlimited) |

For Supabase: set `DATABASE_URL` to your Supabase pooler URL — no code changes.

## Deploy (Docker / Railway)

The Dockerfile installs CPU-only torch from the PyPI CPU index first (the
default CUDA wheel is multi-GB and useless without a GPU) and downloads the
embedding model into the HF cache at BUILD time, so the runtime never makes
network calls — the first request of a fresh container is fast.

```bash
docker build -t agent-platform .
docker run --env-file .env -p 8000:8000 agent-platform
```

Railway: point the service at this repo root (Dockerfile is auto-detected).
Set the env vars above, then run the migrations on the attached Postgres:

```bash
python -m scripts.init_db        # fresh DB
python -m scripts.migrate_settings  # idempotent: users.name/preferences, pinned, usage_events
python -m scripts.migrate_reasoning # idempotent: messages.reasoning
```

> **Heavy deps on a tight disk (dev machines)?** The embedding stack
> (torch + sentence-transformers ≈ 1.5GB + model cache ≈ 0.6GB) can live in
> its own venv on a separate partition with redirected caches, e.g.
> `HF_HOME=/opt/hf-cache PIP_CACHE_DIR=/opt/pip-cache` — deployment
> platforms build their own environment anyway.

## API

All endpoints return JSON. Errors are always `{"error": "..."}` with a proper
HTTP status code.

### Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Register `{email, password}` → `{access_token, user}` |
| `POST` | `/auth/login` | Login `{email, password}` → `{access_token, user}` |

### Projects (agents) — requires `Authorization: Bearer <token>`

| Method | Path | Description |
|---|---|---|
| `POST` | `/projects` | Create `{name, description?, system_prompt?, model?}` |
| `GET` | `/projects` | List my projects |
| `GET` | `/projects/{id}` | Get one project (404 if not yours) |
| `PATCH` | `/projects/{id}` | Partial update |
| `DELETE` | `/projects/{id}` | Delete |

### Conversations & chat — requires auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/projects/{pid}/conversations` | Create `{title?}` |
| `GET` | `/projects/{pid}/conversations` | List |
| `GET` | `/projects/{pid}/conversations/{cid}` | Conversation + messages |
| `POST` | `/projects/{pid}/conversations/{cid}/chat` | Send `{message}` → SSE stream of `provider` / `thinking` (live reasoning) / `tool` / `content` / `done` events; saves user message, calls LLM with system prompt + history, persists assistant reply + reasoning |

Every project/conversation/message query is scoped to the authenticated user —
cross-user access returns 404.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

119 tests: auth, project CRUD + isolation, conversations, chat prompt
construction, SSE event streaming, LLM provider fallback, tool calling
(calculator / search_project_files), upload + RAG, usage metering — fake LLM
and fake storage via dependency injection, no network needed.

## Project layout

```
app/
  main.py          FastAPI app, lifespan (embedder preload), error handlers
  config.py        env-driven settings (incl. fallback provider)
  database.py      engine / session / Base
  models.py        User, Project, Conversation, Message, ProjectFile, FileChunk, UsageEvent
  schemas.py       Pydantic request/response contracts
  security.py      bcrypt + JWT
  dependencies.py  get_current_user (Bearer token)
  llm.py           LLM client (streaming, provider fallback), chat builder
  services.py      ownership helpers
  embeddings.py    nomic-embed-text-v1.5 singleton (task-prefix aware)
  storage.py       Supabase Storage / local-dir boundary
  rag.py           text extraction, chunking, embedding, pgvector search
  tools.py         calculator + search_project_files
  routers/         auth, projects, conversations (SSE), files
scripts/init_db.py           create tables
scripts/migrate_settings.py  idempotent settings/usage migrations
scripts/migrate_reasoning.py idempotent messages.reasoning migration
frontend/          React + Vite UI (login, workspace, canvas, live thinking)
tests/             pytest suite
```

See `ARCHITECTURE.md` for design rationale.

# Agent Platform

A minimal multi-tenant chatbot platform. Users register, create "projects"
(each project is one AI agent with its own system prompt), and chat with their
agent through an LLM (OpenRouter / DeepSeek v4 flash).

Built as a take-home assignment — deliberately minimal: auth, projects,
conversations, chat. No agent frameworks, no RAG (deferred), no streaming.

## Tech stack

- Python 3.11+, FastAPI
- SQLAlchemy 2.0 ORM
- PostgreSQL (local dev; Supabase-compatible — swap the URL)
- JWT auth (python-jose) + bcrypt password hashing (passlib)
- LLM via the official `openai` SDK pointed at OpenRouter's OpenAI-compatible
  endpoint (chat.completions)

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
#       OPENAI_API_KEY=sk-h5J...   (see ~/.local/share/opencode/auth.json)
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

> **Heavy deps (RAG) on a tight disk?** The embedding stack (torch +
> sentence-transformers ≈ 1.5GB + model cache ≈ 0.6GB) can be installed into
> its own venv on a separate partition with the caches redirected, e.g.
> `python3 -m venv /opt/agentplatform-venv` then
> `pip install -r requirements.txt` inside it plus
> `HF_HOME=/opt/hf-cache PIP_CACHE_DIR=/opt/pip-cache` exported when running.
> Deployment platforms build their own environment anyway.

API docs: http://127.0.0.1:8000/docs

## Environment variables (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2:///agent_platform` | SQLAlchemy URL (unix-socket peer auth for local dev) |
| `JWT_SECRET` | `change-me-in-prod` | HMAC secret for JWT signing — set a random value |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token lifetime |
| `OPENAI_API_KEY` | (empty) | Provider API key (OpenRouter `sk-or-v1-...` or opencode-go `sk-h5J...`) |
| `OPENAI_BASE_URL` | `https://openrouter.ai/api/v1` | LLM endpoint (OpenAI-compatible) |
| `DEFAULT_MODEL` | `deepseek/deepseek-v4-flash` | Model when a project sets none |

For Supabase: set `DATABASE_URL` to your Supabase pooler URL — no code changes.

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
| `POST` | `/projects/{pid}/conversations/{cid}/chat` | Send `{message}` → saves user message, calls LLM with system prompt + history, saves + returns reply |

Every project/conversation/message query is scoped to the authenticated user —
cross-user access returns 404.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

21 tests: auth, project CRUD + isolation, conversations, chat prompt
construction, LLM failure handling (fake LLM via dependency injection — no
network needed).

## Project layout

```
app/
  main.py          FastAPI app, global error handlers
  config.py        env-driven settings
  database.py      engine / session / Base
  models.py        User, Project, Conversation, Message
  schemas.py       Pydantic request/response contracts
  security.py      bcrypt + JWT
  dependencies.py  get_current_user (Bearer token)
  llm.py           LLM client (OpenRouter) + chat message builder
  services.py      ownership helpers
  routers/         auth, projects, conversations
scripts/init_db.py  create tables
tests/             pytest suite
```

See `ARCHITECTURE.md` for design rationale.

# Agent Platform — Build Rules

## What this is
A minimal multi-tenant chatbot platform: users register, create "projects"
(each project is one AI agent with its own system prompt), and chat with
their agent via an LLM API.

## Tech stack (fixed, do not substitute)
- Python 3.11+, FastAPI
- SQLAlchemy ORM
- PostgreSQL, hosted on Supabase
- Auth: JWT (python-jose) + password hashing (passlib/bcrypt) — no OAuth2,
  no third-party auth providers
- LLM: OpenAI API (Responses API), called directly via the official `openai`
  Python SDK — no LangChain, no LangGraph, no agent framework

## Core scope — build ONLY this, in this order
1. User registration + login (JWT issued on success)
2. Project CRUD, scoped to the logged-in user (`user_id` foreign key, every
   query filters by it)
3. Each project has: name, description, system_prompt, model
4. Conversations + messages, scoped to a project
5. One chat endpoint: takes a user message, loads conversation history,
   calls OpenAI with the project's system_prompt + history, saves and
   returns the reply
6. File upload + RAG (decision made, in scope): upload .txt/.pdf to a
   project, chunk + embed (hosted Gemini API, gemini-embedding-001, dim 768,
   RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY task types), store vectors in
   Postgres via pgvector, files in Supabase Storage (bucket `project-files`).
   Chat may retrieve top-K matching chunks and inject them as context.
7. Web search tool (decision made, in scope): a `web_search(query: str)`
   tool in the same tool-calling loop as calculator / search_project_files,
   backed by the Tavily API (tavily.com). Gated on the optional `TAVILY_API_KEY`
   env var — when unset, the tool definition is excluded from the tools list
   offered to the model entirely (never offered-then-failed). Network/API
   errors return a graceful "Error: web search unavailable" string to the
   loop; no new loop logic, respects MAX_TOOL_TURNS.

## Explicitly OUT OF SCOPE — do not build these unless told otherwise
- No LangGraph, no multi-agent orchestration, no agent-to-agent routing
- No "skills" system, no slash commands, no mode-switching within a chat
- No generative UI / dynamic frontend components
- No WebSocket streaming (unless explicitly requested later)
- No Prometheus/Grafana, no observability dashboards
- No self-reflection / critic loops
- If a task seems to need one of the above, stop and ask instead of
  building a workaround

## Security rules (non-negotiable)
- Every database query for projects/conversations/messages must filter by
  the authenticated user's ID — no exceptions, no "trust the frontend"
- Passwords are always hashed, never stored or logged in plaintext
- JWT secret and OpenAI API key come from environment variables, never
  hardcoded

## Conventions
- REST endpoints, JSON in/out
- "Project" in code/API == "agent" in user-facing language — keep this
  mapping consistent, don't introduce a separate "agent" concept
- Every error returns a proper HTTP status code + JSON `{"error": "..."}`,
  never an unhandled stack trace

## Build & deploy — Step 7 checklist (decisions made, NOT yet executed)
- Dependencies must be installed ONLY from `requirements.txt`; any new
  import in `app/` must be recorded there in the same change. No ad hoc
  `pip install` into a local venv without updating the manifest (the
  project `.venv` already diverged this way once and could not boot).
- No torch / no HF model downloads: embeddings are hosted Gemini API calls
  (`GEMINI_API_KEY`, free tier). The image is plain python:3.12-slim +
  requirements.txt; there is no startup preload step. Existing vectors
  created with the old nomic model are incompatible — re-upload affected
  project files.
- Post-deploy smoke: cold-start a container, confirm upload+chat latency is
  normal on the very first request.

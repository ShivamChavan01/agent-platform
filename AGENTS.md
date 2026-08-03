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

## Explicitly OUT OF SCOPE — do not build these unless told otherwise
- No LangGraph, no multi-agent orchestration, no agent-to-agent routing
- No pgvector / RAG / embeddings / file upload (decision deferred — ask
  before building)
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

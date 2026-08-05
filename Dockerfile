# ---- Stage 1: build the React frontend ----
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend, serving the built frontend ----
FROM python:3.12-slim

WORKDIR /app

# CPU-only torch FIRST — the default CUDA wheel is multi-GB and useless on
# Railway (no GPU). Smaller image, faster build. Must precede -r requirements.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Embedding model at BUILD time (HF cache), so the runtime never makes
# network calls — embeddings keep working offline in the demo.
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('nomic-ai/nomic-embed-text-v1.5')"

COPY app ./app
COPY --from=frontend /build/dist ./frontend/dist

EXPOSE 8000

# Listen on Railway's injected PORT when present (proxy routes there),
# falling back to 8000 locally.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

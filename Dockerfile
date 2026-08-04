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

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
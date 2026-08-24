"""Embedding boundary — hosted Gemini embeddings (gemini-embedding-001).

No local ML model: vectors come from the Gemini API free tier, so the
container ships no torch and no build-time model download. Document chunks
are embedded with task_type RETRIEVAL_DOCUMENT, search queries with
RETRIEVAL_QUERY (replaces nomic's `search_document:` / `search_query:`
text prefixes). Vectors are requested at settings.embed_dim dimensions and
L2-normalized here — gemini-embedding-001 only auto-normalizes at its full
3072 dims, matching the normalized output of the previous local embedder.
"""

import math
from functools import lru_cache
from typing import Protocol

from app.config import settings

_GEMINI_BATCH = 100


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class _GeminiEmbedder:
    _client = None

    def _get_client(self):
        if self._client is None:
            from google import genai

            if not settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is not configured")
            self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        from google.genai import types

        client = self._get_client()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _GEMINI_BATCH):
            batch = texts[start : start + _GEMINI_BATCH]
            result = client.models.embed_content(
                model=settings.gemini_embed_model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=settings.embed_dim,
                ),
            )
            vectors.extend(_normalize(list(e.values)) for e in result.embeddings)
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


@lru_cache
def get_embedder() -> Embedder:
    return _GeminiEmbedder()

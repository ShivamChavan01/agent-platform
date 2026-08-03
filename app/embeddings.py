"""Embedding boundary.

Model is loaded ONCE as a module-level lazy singleton (never per-request).
nomic-embed-text-v1.5 REQUIRES task prefixes or retrieval quality degrades:
- stored document chunks -> "search_document: "
- search queries       -> "search_query: "
The pipeline applies prefixes in `rag.py` before calling the embedder.

The model is downloaded once at Docker-build time (or into the HF cache on a
dev machine with network). At runtime this module never makes network calls —
the demo must not depend on an external embedding service.
"""

from typing import Protocol

from app.config import settings

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class _LocalEmbedder:
    _instance: "_LocalEmbedder | None" = None
    _model = None

    def __new__(cls) -> "_LocalEmbedder":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(settings.embed_model)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        model = self._load()
        vectors = model.encode([text], normalize_embeddings=True, show_progress_bar=False)
        return vectors[0].tolist()


def get_embedder() -> Embedder:
    return _LocalEmbedder()
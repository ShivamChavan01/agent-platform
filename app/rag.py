"""Chunking, extraction and embedding-pipeline helpers for RAG."""

import io
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import DOCUMENT_PREFIX, QUERY_PREFIX, Embedder
from app.models import FileChunk, Project

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
RETRIEVAL_LIMIT = 4

TEXT_EXTENSIONS = {
    # plain-text-ish formats decoded as UTF-8
    ".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".log",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".xml",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sql", ".sh",
    ".go", ".rs", ".rb", ".c", ".h", ".cpp", ".hpp", ".java", ".kt", ".swift",
}
ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | {".pdf", ".docx"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if size <= overlap:
        raise ValueError("size must be greater than overlap")
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    n = len(text)
    if n <= size:
        return [text]
    while start < n:
        end = min(start + size, n)
        chunks.append(text[start:end])
        if end >= n:
            break
        start = max(start + size - overlap, end - size + 1)
    return chunks


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read the PDF — the file may be corrupt",
        )


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read the DOCX — the file may be corrupt",
        )


def extract_text(filename: str, data: bytes) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type — use .txt/.md/.csv/.json/code files, .pdf, or .docx",
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File exceeds the 10MB size limit",
        )
    if ext == ".pdf":
        return _extract_pdf(data)
    if ext == ".docx":
        return _extract_docx(data)
    return data.decode("utf-8", errors="replace")


def embed_chunks(embedder: Embedder, chunks: list[str]) -> list[list[float]]:
    # Task prefix is REQUIRED for nomic-embed-text-v1.5 retrieval quality.
    prefixed = [f"{DOCUMENT_PREFIX}{c}" for c in chunks]
    return embedder.embed_documents(prefixed)


def embed_query(embedder: Embedder, query: str) -> list[float]:
    return embedder.embed_query(f"{QUERY_PREFIX}{query}")


def search_chunks(
    db: Session, project_id: uuid.UUID, query_vector: list[float], limit: int = RETRIEVAL_LIMIT
) -> list[str]:
    rows = db.scalars(
        select(FileChunk.content)
        .where(FileChunk.project_id == project_id)
        .order_by(FileChunk.embedding.l2_distance(query_vector))
        .limit(limit)
    ).all()
    return list(rows)
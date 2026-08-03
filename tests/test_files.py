import pytest

from app.embeddings import DOCUMENT_PREFIX, QUERY_PREFIX
from app.rag import chunk_text
from conftest import auth_headers, register

TINY_TXT = b"Hello RAG world. This project supports file uploads."


@pytest.fixture
def project_token(client):
    token = register(client).json()["access_token"]
    resp = client.post(
        "/projects",
        headers=auth_headers(token),
        json={"name": "Doc Assistant"},
    )
    return token, resp.json()["id"]


def upload(client, token, pid, filename="notes.txt", content=None, content_type="text/plain"):
    files = {"file": (filename, content if content is not None else TINY_TXT, content_type)}
    return client.post(
        f"/projects/{pid}/files", headers=auth_headers(token), files=files
    )


# ---------- Chunking (pure logic, TDD) ----------


def test_chunk_text_short_input_single_chunk():
    assert chunk_text("short text") == ["short text"]


def test_chunk_text_empty_and_whitespace():
    assert chunk_text("   \n  ") == []
    assert chunk_text("") == []


def test_chunk_text_two_chunks_with_overlap():
    text = "0123456789" * 200  # 2000 chars
    chunks = chunk_text(text, size=1000, overlap=150)
    assert len(chunks) == 3  # starts at 0, 850, 1700
    # each subsequent chunk re-embeds the previous chunk's tail (overlap)
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.startswith(prev[-150:])
    # full original text is covered, overlap makes total longer
    assert set(text) == set("".join(chunks))
    assert sum(len(c) for c in chunks) > len(text)


def test_chunk_text_three_chunks_reassemble():
    text = "0123456789" * 300  # 3000 chars
    chunks = chunk_text(text, size=1000, overlap=150)
    assert len(chunks) == 4  # starts at 0, 850, 1700, 2550
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.startswith(prev[-150:])


# ---------- Embedding prefix (TDD: prefix must exist before embed call) ----------


def test_embed_prefix_constants():
    assert DOCUMENT_PREFIX == "search_document: "
    assert QUERY_PREFIX == "search_query: "


def test_upload_prefixes_documents_before_embed(client, project_token, fake_embedder):
    token, pid = project_token
    resp = upload(client, token, pid, content="apple banana orange" * 400)
    assert resp.status_code == 201
    assert fake_embedder.embed_documents_calls
    for call in fake_embedder.embed_documents_calls:
        assert call.startswith(DOCUMENT_PREFIX)


# ---------- Upload acceptance / validation ----------


def test_upload_txt_returns_record_with_chunks(client, project_token, fake_embedder):
    token, pid = project_token
    resp = upload(client, token, pid, filename="notes.txt")
    assert resp.status_code == 201
    body = resp.json()
    assert body["original_filename"] == "notes.txt"
    assert body["size_bytes"] == len(TINY_TXT)
    assert body["chunk_count"] == 1
    assert body["storage_path"].startswith(f"{pid}/")


def test_embeddings_persisted_in_pg_vector_column(
    client, db_session, project_token, fake_embedder
):
    from sqlalchemy import select

    from app.models import FileChunk

    token, pid = project_token
    resp = upload(client, token, pid, filename="notes.txt")
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    chunks = db_session.scalars(
        select(FileChunk).where(FileChunk.file_id == file_id)
    ).all()
    assert len(chunks) == 1
    assert len(chunks[0].embedding) == 768
    raw = db_session.execute(
        select(FileChunk.embedding).where(FileChunk.id == chunks[0].id)
    ).scalar()
    assert isinstance(raw, list) and len(raw) == 768


def test_upload_bad_extension_400(client, project_token):
    token, pid = project_token
    resp = upload(client, token, pid, filename="malware.exe", content=b"MZ...")
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_upload_empty_file_400(client, project_token):
    token, pid = project_token
    resp = upload(client, token, pid, content=b"")
    assert resp.status_code == 400


def test_upload_pdf_requires_real_bytes(client, project_token):
    token, pid = project_token
    resp = upload(
        client,
        token,
        pid,
        filename="notes.pdf",
        content=b"not actually a pdf",
        content_type="application/pdf",
    )
    assert resp.status_code == 400


def test_upload_requires_auth(client, project_token):
    _, pid = project_token
    resp = client.post(
        f"/projects/{pid}/files",
        files={"file": ("notes.txt", TINY_TXT, "text/plain")},
    )
    assert resp.status_code == 401


def test_upload_other_users_project_404(client, project_token):
    token_a, pid = project_token
    token_b = register(client, email="b@example.com").json()["access_token"]
    resp = upload(client, token_b, pid)
    assert resp.status_code == 404


# ---------- Listing / ownership ----------


def test_list_files_scoped_to_project(client, project_token, fake_embedder):
    token, pid = project_token

    second = client.post(
        "/projects", headers=auth_headers(token), json={"name": "Second"}
    ).json()["id"]

    upload(client, token, pid, filename="a.txt")
    upload(client, token, pid, filename="b.txt")
    upload(client, token, second, filename="c.txt")

    resp = client.get(f"/projects/{pid}/files", headers=auth_headers(token))
    assert resp.status_code == 200
    names = {f["original_filename"] for f in resp.json()}
    assert names == {"a.txt", "b.txt"}

    resp2 = client.get(f"/projects/{second}/files", headers=auth_headers(token))
    assert [f["original_filename"] for f in resp2.json()] == ["c.txt"]


def test_list_files_other_users_project_404(client, project_token):
    token_a, pid = project_token
    token_b = register(client, email="b@example.com").json()["access_token"]
    resp = client.get(f"/projects/{pid}/files", headers=auth_headers(token_b))
    assert resp.status_code == 404
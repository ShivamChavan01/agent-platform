import base64

import pytest

from app.llm import get_llm_client
from conftest import auth_headers, chat_events, done_event, register

SYSTEM_PROMPT = "You are a helpful support agent."


class FakeLLM:
    def __init__(self, reply="fake assistant reply", thinking="reasoning out loud"):
        self.reply = reply
        self.thinking = thinking
        self.calls = []

    def stream(self, model, messages, tools=None):
        self.calls.append((model, list(messages)))
        if self.thinking:
            yield {"type": "thinking", "text": self.thinking}
        if self.reply:
            yield {"type": "content", "text": self.reply}
        yield {
            "type": "result",
            "content": self.reply,
            "reasoning": self.thinking,
            "tool_calls": None,
            "usage": None,
            "provider": "primary",
            "model": model,
        }


class FailingLLM:
    def stream(self, model, messages, tools=None):
        raise RuntimeError("llm down")
        yield  # pragma: no cover


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def project_token(client):
    token = register(client).json()["access_token"]
    resp = client.post(
        "/projects",
        headers=auth_headers(token),
        json={
            "name": "Support Bot",
            "system_prompt": SYSTEM_PROMPT,
            "model": "deepseek/deepseek-v4-flash",
        },
    )
    return token, resp.json()["id"]


@pytest.fixture
def use_fake_llm(client, fake_llm):
    client.app.dependency_overrides[get_llm_client] = lambda: fake_llm
    yield fake_llm
    client.app.dependency_overrides.pop(get_llm_client, None)


def create_conversation(client, token, pid):
    return client.post(
        f"/projects/{pid}/conversations",
        headers=auth_headers(token),
        json={"title": "My Chat"},
    )


def test_create_and_list_conversations(client, project_token):
    token, pid = project_token
    resp = create_conversation(client, token, pid)
    assert resp.status_code == 201
    cid = resp.json()["id"]
    assert resp.json()["project_id"] == pid

    listed = client.get(
        f"/projects/{pid}/conversations", headers=auth_headers(token)
    ).json()
    assert [c["id"] for c in listed] == [cid]


def test_chat_streams_thinking_then_reply_and_persists(client, project_token, use_fake_llm):
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]

    resp, events = chat_events(client, token, pid, cid, "Hi there")
    assert resp.headers["content-type"].startswith("text/event-stream")

    thinking = [ev for ev in events if ev["event"] == "thinking"]
    assert thinking and thinking[0]["delta"] == "reasoning out loud"

    content = "".join(ev["delta"] for ev in events if ev["event"] == "content")
    assert content == "fake assistant reply"

    done = done_event(events)
    assert done is not None
    assert done["content"] == "fake assistant reply"
    assert done["model"] == "deepseek/deepseek-v4-flash"
    assert done["provider"] == "primary"
    assert done["reasoning"] == "reasoning out loud"

    detail = client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)
    ).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][0]["content"] == "Hi there"
    # reasoning is persisted in its own field, never leaked into content
    assert detail["messages"][1]["reasoning"] == "reasoning out loud"
    assert all("reasoning" not in (m["content"] or "") for m in detail["messages"])


def test_chat_sends_system_prompt_model_and_history(client, project_token, use_fake_llm):
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]
    for msg in ["first question", "second question"]:
        chat_events(client, token, pid, cid, msg)

    model, messages = use_fake_llm.calls[-1]
    assert model == "deepseek/deepseek-v4-flash"
    assert messages[0]["role"] == "system"
    assert messages[0]["content"].startswith(SYSTEM_PROMPT)
    assert "deepseek/deepseek-v4-flash" in messages[0]["content"]
    assert messages[1:] == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "fake assistant reply"},
        {"role": "user", "content": "second question"},
    ]


def test_chat_requires_auth(client, project_token):
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]
    resp = client.post(f"/projects/{pid}/conversations/{cid}/chat", json={"message": "hi"})
    assert resp.status_code == 401


def test_chat_other_users_conversation_404(client, project_token):
    token_a, pid = project_token
    cid = create_conversation(client, token_a, pid).json()["id"]
    token_b = register(client, email="b@example.com").json()["access_token"]

    resp = client.post(
        f"/projects/{pid}/conversations/{cid}/chat",
        headers=auth_headers(token_b),
        json={"message": "hi"},
    )
    assert resp.status_code == 404

    resp = client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token_b)
    )
    assert resp.status_code == 404


def test_chat_llm_failure_emits_error_event_and_keeps_user_message(client, project_token):
    client.app.dependency_overrides[get_llm_client] = FailingLLM
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]

    _, events = chat_events(client, token, pid, cid, "hi")
    client.app.dependency_overrides.pop(get_llm_client, None)

    errors = [ev for ev in events if ev["event"] == "error"]
    assert len(errors) == 1
    assert "model" in errors[0]["error"].lower()
    assert done_event(events) is None

    detail = client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)
    ).json()
    assert [m["role"] for m in detail["messages"]] == ["user"]


def make_pdf(text=b"Shivam Chavan Resume"):
    """A minimal but valid single-page PDF (correct xref offsets)."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = b"BT /F1 12 Tf 72 720 Td (" + text + b") Tj ET"
    objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def last_user_message(use_fake_llm):
    return use_fake_llm.calls[-1][1][-1]["content"]


def test_chat_attachment_pdf_is_extracted_not_binary(client, project_token, use_fake_llm):
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]

    resp = client.post(
        f"/projects/{pid}/conversations/{cid}/chat",
        headers=auth_headers(token),
        json={
            "message": "Summarize this file",
            "attachments": [
                {"filename": "resume.pdf", "content_b64": base64.b64encode(make_pdf()).decode()}
            ],
        },
    )
    assert resp.status_code == 200
    content = last_user_message(use_fake_llm)
    assert "resume.pdf" in content
    assert "Shivam Chavan Resume" in content
    assert "%PDF" not in content
    assert "could not read" not in content


def test_chat_attachment_txt_is_decoded(client, project_token, use_fake_llm):
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]

    resp = client.post(
        f"/projects/{pid}/conversations/{cid}/chat",
        headers=auth_headers(token),
        json={
            "message": "Read this",
            "attachments": [
                {"filename": "notes.txt", "content_b64": base64.b64encode(b"hello from notes").decode()}
            ],
        },
    )
    assert resp.status_code == 200
    assert "hello from notes" in last_user_message(use_fake_llm)


def test_chat_attachment_corrupt_pdf_degrades_gracefully(client, project_token, use_fake_llm):
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]

    resp = client.post(
        f"/projects/{pid}/conversations/{cid}/chat",
        headers=auth_headers(token),
        json={
            "message": "What is in here?",
            "attachments": [
                {"filename": "broken.pdf", "content_b64": base64.b64encode(b"not actually a pdf").decode()}
            ],
        },
    )
    assert resp.status_code == 200
    content = last_user_message(use_fake_llm)
    assert "could not read broken.pdf" in content
    assert "not actually a pdf" not in content


def test_chat_attachment_unsupported_type_degrades_gracefully(client, project_token, use_fake_llm):
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]

    resp = client.post(
        f"/projects/{pid}/conversations/{cid}/chat",
        headers=auth_headers(token),
        json={
            "message": "What is in here?",
            "attachments": [
                {"filename": "archive.zip", "content_b64": base64.b64encode(b"PK\x03\x04junk").decode()}
            ],
        },
    )
    assert resp.status_code == 200
    assert "could not read archive.zip" in last_user_message(use_fake_llm)


def test_chat_attachment_text_is_truncated(client, project_token, use_fake_llm):
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]
    big = b"word " * 12_000  # ~60KB of plain text

    resp = client.post(
        f"/projects/{pid}/conversations/{cid}/chat",
        headers=auth_headers(token),
        json={
            "message": "Read this",
            "attachments": [
                {"filename": "big.txt", "content_b64": base64.b64encode(big).decode()}
            ],
        },
    )
    assert resp.status_code == 200
    content = last_user_message(use_fake_llm)
    assert "File text truncated" in content
    assert len(content) < 45_000

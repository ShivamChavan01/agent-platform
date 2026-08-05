from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.config import settings
from app.llm import get_llm_client
from app.models import Message, UsageEvent
from conftest import auth_headers, chat_events, done_event, register


def create_project(client, token, **overrides):
    return client.post(
        "/projects",
        headers=auth_headers(token),
        json={"name": "Bot", "model": "deepseek/deepseek-v4-flash", **overrides},
    )


def create_conversation(client, token, pid, title="Chat"):
    return client.post(
        f"/projects/{pid}/conversations",
        headers=auth_headers(token),
        json={"title": title},
    )


class UsageLLM:
    def __init__(self, content="ok", usage=None):
        self.content = content
        self.usage = usage
        self.calls = []

    def stream(self, model, messages, tools=None, reasoning_effort=None):
        self.calls.append((model, list(messages), tools))
        if self.content:
            yield {"type": "content", "text": self.content}
        yield {
            "type": "result",
            "content": self.content,
            "tool_calls": None,
            "usage": self.usage,
            "provider": "primary",
            "model": model,
        }


def use_llm(client, llm):
    client.app.dependency_overrides[get_llm_client] = lambda: llm
    return llm


# ---------- Profile ----------


def test_get_me_returns_profile(client):
    token = register(client, name="Alice").json()["access_token"]
    resp = client.get("/auth/me", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"
    assert resp.json()["name"] == "Alice"


def test_get_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_patch_me_updates_name(client):
    token = register(client).json()["access_token"]
    resp = client.patch("/auth/me", headers=auth_headers(token), json={"name": "Shivam"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Shivam"
    assert resp.json()["email"] == "user@example.com"

    again = client.patch("/auth/me", headers=auth_headers(token), json={"name": "S."})
    assert again.json()["name"] == "S."


def test_patch_me_requires_auth(client):
    assert client.patch("/auth/me", json={"name": "X"}).status_code == 401


def test_register_accepts_optional_name(client):
    resp = register(client, name="Alice")
    assert resp.status_code == 201
    assert resp.json()["user"]["name"] == "Alice"


def test_patch_me_rejects_oversized_name(client):
    token = register(client).json()["access_token"]
    resp = client.patch("/auth/me", headers=auth_headers(token), json={"name": "x" * 300})
    assert resp.status_code == 422


# ---------- Preferences ----------


def test_preferences_default_empty(client):
    token = register(client).json()["access_token"]
    resp = client.get("/auth/me/preferences", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == {}


def test_preferences_update_and_read(client):
    token = register(client).json()["access_token"]
    resp = client.patch(
        "/auth/me/preferences",
        headers=auth_headers(token),
        json={"default_model": "deepseek/deepseek-v4-flash", "context_window": 40},
    )
    assert resp.status_code == 200
    assert resp.json()["default_model"] == "deepseek/deepseek-v4-flash"
    assert resp.json()["context_window"] == 40

    got = client.get("/auth/me/preferences", headers=auth_headers(token)).json()
    assert got == {"default_model": "deepseek/deepseek-v4-flash", "context_window": 40}


def test_preferences_validation(client):
    token = register(client).json()["access_token"]
    assert (
        client.patch(
            "/auth/me/preferences",
            headers=auth_headers(token),
            json={"default_model": "x" * 300},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/auth/me/preferences", headers=auth_headers(token), json={"context_window": 0}
        ).status_code
        == 422
    )


def test_default_model_preference_feeds_project_creation(client):
    token = register(client).json()["access_token"]
    client.patch(
        "/auth/me/preferences",
        headers=auth_headers(token),
        json={"default_model": "deepseek/deepseek-r1"},
    )
    resp = create_project(client, token, model=None)
    assert resp.status_code == 201
    assert resp.json()["model"] == "deepseek/deepseek-r1"


# ---------- Clear conversations (global) ----------


def test_clear_conversations_global_scope(client):
    token_a = register(client, email="a@example.com").json()["access_token"]
    p1 = create_project(client, token_a).json()["id"]
    p2 = create_project(client, token_a, name="Second").json()["id"]
    for pid in (p1, p2):
        create_conversation(client, token_a, pid)
        create_conversation(client, token_a, pid)

    token_b = register(client, email="b@example.com").json()["access_token"]
    p_b = create_project(client, token_b).json()["id"]
    cid_b = create_conversation(client, token_b, p_b).json()["id"]

    resp = client.delete("/auth/me/conversations", headers=auth_headers(token_a))
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 4}

    listed = client.get("/projects", headers=auth_headers(token_a)).json()
    assert len(listed) == 2  # projects survive
    for pid in (p1, p2):
        convs = client.get(
            f"/projects/{pid}/conversations", headers=auth_headers(token_a)
        ).json()
        assert convs == []

    # Other user untouched
    assert client.get(f"/projects/{p_b}/conversations", headers=auth_headers(token_b)).json() != []
    assert client.get(
        f"/projects/{p_b}/conversations/{cid_b}", headers=auth_headers(token_b)
    ).status_code == 200


def test_clear_conversations_removes_messages_not_files(client, db_session):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    cid = create_conversation(client, token, pid).json()["id"]
    up = client.post(
        f"/projects/{pid}/files",
        headers=auth_headers(token),
        files={"file": ("memo.txt", b"lease expires December 2026" * 100, "text/plain")},
    )
    assert up.status_code == 201

    llm = UsageLLM()
    use_llm(client, llm)
    chat_events(client, token, pid, cid, "hi")
    assert db_session.query(Message).count() == 2

    resp = client.delete("/auth/me/conversations", headers=auth_headers(token))
    assert resp.json() == {"deleted": 1}
    assert db_session.query(Message).count() == 0
    assert client.get(f"/projects/{pid}/files", headers=auth_headers(token)).json() != []


def test_clear_conversations_zero_when_none(client):
    token = register(client).json()["access_token"]
    resp = client.delete("/auth/me/conversations", headers=auth_headers(token))
    assert resp.json() == {"deleted": 0}


# ---------- Delete account ----------


def test_delete_account_cascades_everything_and_cleans_storage(client, db_session, fake_storage):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    cid = create_conversation(client, token, pid).json()["id"]
    up = client.post(
        f"/projects/{pid}/files",
        headers=auth_headers(token),
        files={"file": ("memo.txt", b"some content" * 200, "text/plain")},
    )
    assert up.status_code == 201
    storage_path = up.json()["storage_path"]

    llm = UsageLLM(usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3, total_tokens=8))
    use_llm(client, llm)
    chat_events(client, token, pid, cid, "hi")
    assert db_session.query(UsageEvent).count() == 1

    resp = client.delete("/auth/me", headers=auth_headers(token))
    assert resp.status_code == 204

    assert storage_path in fake_storage.deletes
    assert client.post(
        "/auth/login", json={"email": "user@example.com", "password": "password123"}
    ).status_code == 401
    assert client.get(f"/projects/{pid}", headers=auth_headers(token)).status_code == 401
    assert db_session.query(UsageEvent).count() == 0


def test_delete_account_other_user_untouched(client):
    token_a = register(client, email="a@example.com").json()["access_token"]
    token_b = register(client, email="b@example.com").json()["access_token"]
    p_b = create_project(client, token_b).json()["id"]

    assert client.delete("/auth/me", headers=auth_headers(token_a)).status_code == 204
    assert client.get("/projects", headers=auth_headers(token_b)).json()[0]["id"] == p_b


# ---------- Conversation thread actions ----------


def test_patch_conversation_title_and_pin(client):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    cid = create_conversation(client, token, pid).json()["id"]

    resp = client.patch(
        f"/projects/{pid}/conversations/{cid}",
        headers=auth_headers(token),
        json={"title": "Renamed", "pinned": True},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed"
    assert resp.json()["pinned"] is True

    listed = client.get(f"/projects/{pid}/conversations", headers=auth_headers(token)).json()
    assert listed[0]["id"] == cid
    assert listed[0]["pinned"] is True


def test_patch_conversation_partial(client):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    cid = create_conversation(client, token, pid).json()["id"]

    resp = client.patch(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token), json={"pinned": True}
    )
    assert resp.json()["pinned"] is True
    assert resp.json()["title"] == "Chat"


def test_patch_conversation_other_user_404(client):
    token_a = register(client, email="a@example.com").json()["access_token"]
    pid = create_project(client, token_a).json()["id"]
    cid = create_conversation(client, token_a, pid).json()["id"]
    token_b = register(client, email="b@example.com").json()["access_token"]

    resp = client.patch(
        f"/projects/{pid}/conversations/{cid}",
        headers=auth_headers(token_b),
        json={"title": "Hijack"},
    )
    assert resp.status_code == 404


def test_pinned_sorts_first(client):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    c1 = create_conversation(client, token, pid, title="first").json()["id"]
    c2 = create_conversation(client, token, pid, title="second").json()["id"]
    client.patch(
        f"/projects/{pid}/conversations/{c2}", headers=auth_headers(token), json={"pinned": True}
    )
    listed = client.get(f"/projects/{pid}/conversations", headers=auth_headers(token)).json()
    assert [c["id"] for c in listed] == [c2, c1]


def test_delete_conversation_cascades_messages(client, db_session):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    cid = create_conversation(client, token, pid).json()["id"]

    llm = UsageLLM()
    use_llm(client, llm)
    chat_events(client, token, pid, cid, "hi")
    assert db_session.query(Message).count() == 2

    assert (
        client.delete(f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)).status_code
        == 204
    )
    assert client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)
    ).status_code == 404
    assert db_session.query(Message).count() == 0


def test_delete_conversation_other_user_404(client):
    token_a = register(client, email="a@example.com").json()["access_token"]
    pid = create_project(client, token_a).json()["id"]
    cid = create_conversation(client, token_a, pid).json()["id"]
    token_b = register(client, email="b@example.com").json()["access_token"]

    resp = client.delete(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token_b)
    )
    assert resp.status_code == 404


# ---------- Usage metering ----------


def test_chat_records_usage_event(client, db_session):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    cid = create_conversation(client, token, pid).json()["id"]

    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    use_llm(client, UsageLLM(content="reply", usage=usage))
    _, events = chat_events(client, token, pid, cid, "hi")
    done = done_event(events)
    assert done is not None
    assert done["content"] == "reply"
    assert done["usage"] == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }

    row = db_session.query(UsageEvent).one()
    assert row.prompt_tokens == 10
    assert row.completion_tokens == 5
    assert row.total_tokens == 15
    assert row.user_id is not None


def test_chat_without_usage_records_nothing(client, db_session):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    cid = create_conversation(client, token, pid).json()["id"]

    use_llm(client, UsageLLM(content="reply", usage=None))
    _, events = chat_events(client, token, pid, cid, "hi")
    assert done_event(events) is not None
    assert db_session.query(UsageEvent).count() == 0


def test_usage_endpoint_aggregates_in_window(client, db_session):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    cid = create_conversation(client, token, pid).json()["id"]

    use_llm(client, UsageLLM(content="a", usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)))
    chat_events(client, token, pid, cid, "one")
    use_llm(client, UsageLLM(content="b", usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10, total_tokens=30)))
    chat_events(client, token, pid, cid, "two")

    resp = client.get("/auth/me/usage", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["requests"] == 2
    assert body["total_tokens"] == 45
    assert body["prompt_tokens"] == 30
    assert body["completion_tokens"] == 15


def test_usage_window_excludes_old_events(client, db_session):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    cid = create_conversation(client, token, pid).json()["id"]

    use_llm(client, UsageLLM(content="a", usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)))
    chat_events(client, token, pid, cid, "one")
    row = db_session.query(UsageEvent).one()
    row.created_at = datetime.now(timezone.utc) - timedelta(hours=5)
    db_session.commit()

    body = client.get("/auth/me/usage?window_hours=1", headers=auth_headers(token)).json()
    assert body["requests"] == 0
    assert body["total_tokens"] == 0

    body = client.get("/auth/me/usage?window_hours=24", headers=auth_headers(token)).json()
    assert body["requests"] == 1


def test_usage_scoped_per_user(client, db_session):
    token_a = register(client, email="a@example.com").json()["access_token"]
    pid = create_project(client, token_a).json()["id"]
    cid = create_conversation(client, token_a, pid).json()["id"]
    use_llm(client, UsageLLM(content="a", usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3, total_tokens=10)))
    chat_events(client, token_a, pid, cid, "hi")

    token_b = register(client, email="b@example.com").json()["access_token"]
    body = client.get("/auth/me/usage", headers=auth_headers(token_b)).json()
    assert body["requests"] == 0
    assert body["total_tokens"] == 0


def test_daily_token_limit_429_when_configured(client, monkeypatch):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]
    cid = create_conversation(client, token, pid).json()["id"]
    use_llm(client, UsageLLM(content="a", usage=SimpleNamespace(prompt_tokens=8, completion_tokens=2, total_tokens=10)))

    monkeypatch.setattr(settings, "usage_daily_token_limit", 15)
    _, first = chat_events(client, token, pid, cid, "one")
    assert done_event(first) is not None

    # Second call crosses the limit mid-stream: in-band error event, no done.
    _, second = chat_events(client, token, pid, cid, "two")
    assert done_event(second) is None
    errors = [ev for ev in second if ev["event"] == "error"]
    assert len(errors) == 1
    assert "limit" in errors[0]["error"]

    # Already over the limit: rejected at the door with HTTP 429.
    blocked = client.post(
        f"/projects/{pid}/conversations/{cid}/chat",
        headers=auth_headers(token),
        json={"message": "three"},
    )
    assert blocked.status_code == 429
    assert "error" in blocked.json()
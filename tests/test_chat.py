import pytest

from app.llm import get_llm_client
from conftest import auth_headers, register

SYSTEM_PROMPT = "You are a helpful support agent."


class FakeLLM:
    def __init__(self, reply="fake assistant reply"):
        self.reply = reply
        self.calls = []

    def complete(self, model, messages):
        self.calls.append((model, list(messages)))
        return self.reply


class FailingLLM:
    def complete(self, model, messages):
        raise RuntimeError("llm down")


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


def test_chat_returns_reply_and_persists_messages(client, project_token, use_fake_llm):
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]

    resp = client.post(
        f"/projects/{pid}/conversations/{cid}/chat",
        headers=auth_headers(token),
        json={"message": "Hi there"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "fake assistant reply"
    assert resp.json()["role"] == "assistant"

    detail = client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)
    ).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][0]["content"] == "Hi there"


def test_chat_sends_system_prompt_model_and_history(client, project_token, use_fake_llm):
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]
    for msg in ["first question", "second question"]:
        client.post(
            f"/projects/{pid}/conversations/{cid}/chat",
            headers=auth_headers(token),
            json={"message": msg},
        )

    model, messages = use_fake_llm.calls[-1]
    assert model == "deepseek/deepseek-v4-flash"
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
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


def test_chat_llm_failure_returns_502_and_keeps_user_message(client, project_token):
    client.app.dependency_overrides[get_llm_client] = FailingLLM
    token, pid = project_token
    cid = create_conversation(client, token, pid).json()["id"]

    resp = client.post(
        f"/projects/{pid}/conversations/{cid}/chat",
        headers=auth_headers(token),
        json={"message": "hi"},
    )
    client.app.dependency_overrides.pop(get_llm_client, None)
    assert resp.status_code == 502
    assert "error" in resp.json()

    detail = client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)
    ).json()
    assert [m["role"] for m in detail["messages"]] == ["user"]

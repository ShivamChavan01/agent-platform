import json

import pytest

from app.config import settings
from app.llm import get_llm_client
from app.models import Message
from app.tools import TOOLS, available_tools, evaluate_expression, execute_tool
from conftest import auth_headers, chat_events, done_event, register


# ---------- Evaluator (pure logic) ----------


def test_calculator_basic_arithmetic():
    assert evaluate_expression("2 + 3 * 4") == "14"
    assert evaluate_expression("(3 + 5) * 2") == "16"
    assert evaluate_expression("10 / 4") == "2.5"


def test_calculator_unary_and_floats():
    assert evaluate_expression("-7") == "-7"
    assert evaluate_expression("2 ** 3") == "8"


@pytest.mark.parametrize(
    "bad",
    [
        "__import__('os')",
        "eval('1')",
        "1:0",
        "import os",
        "sys.exit()",
        "2 ** 1000000000",
        "0 / 0",
    ],
)
def test_calculator_rejects_unsafe_or_invalid(bad):
    result = execute_tool("calculator", {"expression": bad}, db=None, project_id=None, embedder=None)
    assert result.startswith("Error")


def test_unknown_tool_name_raises():
    with pytest.raises(ValueError):
        execute_tool("not_a_tool", {}, db=None, project_id=None, embedder=None)


def test_tool_definitions_are_consistent():
    names = {t["function"]["name"] for t in TOOLS}
    assert names == {"calculator", "search_project_files", "web_search"}


# ---------- web_search (Tavily) ----------


def test_web_search_excluded_from_offered_tools_without_api_key():
    assert {t["function"]["name"] for t in available_tools()} == {
        "calculator",
        "search_project_files",
    }


def test_web_search_included_when_api_key_set(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-key")
    assert "web_search" in {t["function"]["name"] for t in available_tools()}


def test_web_search_formats_results(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(
        "app.tools._tavily_search",
        lambda query: [
            {"title": "Python Programming Language", "url": "https://www.python.org/", "content": "Python is a programming language."},
            {"title": "OpenAI API", "url": "https://platform.openai.com/", "content": "Build AI applications with the OpenAI API."},
        ],
    )
    result = execute_tool("web_search", {"query": "python"}, db=None, project_id=None, embedder=None)
    assert "Python Programming Language" in result
    assert "https://www.python.org/" in result
    assert "Python is a programming language." in result
    assert "OpenAI API" in result
    assert "\n\n---\n\n" in result


def test_web_search_empty_query_returns_error():
    result = execute_tool("web_search", {"query": "   "}, db=None, project_id=None, embedder=None)
    assert result == "Error: query must be a non-empty string"


def test_web_search_no_api_key_returns_error():
    result = execute_tool("web_search", {"query": "python"}, db=None, project_id=None, embedder=None)
    assert result == "Error: web search unavailable"


def test_web_search_api_failure_returns_error(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-key")
    monkeypatch.setattr("app.tools._tavily_search", lambda query: (_ for _ in ()).throw(RuntimeError("boom")))
    result = execute_tool("web_search", {"query": "python"}, db=None, project_id=None, embedder=None)
    assert result == "Error: web search unavailable"


def test_web_search_no_results_returns_note(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-key")
    monkeypatch.setattr("app.tools._tavily_search", lambda query: [])
    result = execute_tool("web_search", {"query": "nothing relevant"}, db=None, project_id=None, embedder=None)
    assert "No results" in result


def test_chat_with_web_search_tool_grounds_answer(client, conv, monkeypatch):
    token, pid, cid = conv
    monkeypatch.setattr(settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(
        "app.tools._tavily_search",
        lambda query: [
            {"title": "Python 3 Release", "url": "https://www.python.org/3.13/", "content": "Python 3.13 is the latest stable release."}
        ],
    )
    llm = ScriptedLLM(
        [
            Msg(tool_calls=[ToolCall("call_w", "web_search", '{"query": "python latest release"}')], thinking="searching"),
            Msg(content="The latest stable release is **Python 3.13**."),
        ]
    )
    overrides(client, llm)

    _, events = chat_events(client, token, pid, cid, "What is the latest Python release?")
    done = done_event(events)
    assert done is not None
    assert done["content"] == "The latest stable release is **Python 3.13**."

    tool_events = [ev for ev in events if ev["event"] == "tool"]
    assert tool_events and tool_events[0]["name"] == "web_search"

    detail = client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)
    ).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "tool", "assistant"]
    tool_msg = detail["messages"][2]
    assert tool_msg["tool_name"] == "web_search"
    assert "Python 3 Release" in tool_msg["content"]
    assert "https://www.python.org/3.13/" in tool_msg["content"]


def test_chat_web_search_failure_does_not_crash_request(client, conv, monkeypatch):
    token, pid, cid = conv
    monkeypatch.setattr(settings, "tavily_api_key", "test-key")
    monkeypatch.setattr("app.tools._tavily_search", lambda query: (_ for _ in ()).throw(RuntimeError("boom")))
    llm = ScriptedLLM(
        [
            Msg(tool_calls=[ToolCall("call_f", "web_search", '{"query": "anything"}')]),
            Msg(content="I could not reach the web search service."),
        ]
    )
    overrides(client, llm)

    _, events = chat_events(client, token, pid, cid, "hi")
    assert done_event(events) is not None
    assert done_event(events)["content"] == "I could not reach the web search service."

    detail = client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)
    ).json()
    tool_msg = detail["messages"][2]
    assert tool_msg["tool_name"] == "web_search"
    assert tool_msg["content"] == "Error: web search unavailable"


# ---------- Chat tool loop (HTTP, scripted FakeLLM) ----------


class ToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = FunctionCall(name, arguments)


class FunctionCall:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class Msg:
    def __init__(self, content=None, tool_calls=None, thinking=None, usage=None):
        self.content = content
        self.tool_calls = tool_calls
        self.thinking = thinking
        self.usage = usage


class ScriptedLLM:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.index = 0

    def stream(self, model, messages, tools=None):
        self.calls.append((model, [dict(m) for m in messages], tools))
        out = self.script[min(self.index, len(self.script) - 1)]
        self.index += 1
        if out.thinking:
            yield {"type": "thinking", "text": out.thinking}
        if out.content:
            yield {"type": "content", "text": out.content}
        calls = None
        if out.tool_calls:
            calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in out.tool_calls
            ]
            for tc in calls:
                yield {"type": "tool", **tc["function"], "id": tc["id"]}
        yield {
            "type": "result",
            "content": out.content or "",
            "reasoning": out.thinking,
            "tool_calls": calls,
            "usage": out.usage,
            "provider": "primary",
            "model": model,
        }


@pytest.fixture
def project_token(client):
    token = register(client).json()["access_token"]
    resp = client.post(
        "/projects",
        headers=auth_headers(token),
        json={"name": "Bot", "system_prompt": "You are helpful.", "model": "test/llm"},
    )
    return token, resp.json()["id"]


@pytest.fixture
def conv(client, project_token):
    token, pid = project_token
    resp = client.post(
        f"/projects/{pid}/conversations",
        headers=auth_headers(token),
        json={"title": "c"},
    )
    return token, pid, resp.json()["id"]


def overrides(client, llm):
    client.app.dependency_overrides[get_llm_client] = lambda: llm
    return llm


def test_chat_with_calculator_tool_persists_tool_messages(client, conv):
    token, pid, cid = conv
    llm = ScriptedLLM(
        [
            Msg(tool_calls=[ToolCall("call_1", "calculator", '{"expression": "17 * 23 + 4"}')], thinking="computing"),
            Msg(content="The result of 17 * 23 + 4 is **395**."),
        ]
    )
    overrides(client, llm)

    _, events = chat_events(client, token, pid, cid, "What is 17 * 23 + 4?")
    done = done_event(events)
    assert done is not None
    assert done["content"] == "The result of 17 * 23 + 4 is **395**."

    # live tool events emitted while the model calls the calculator
    tool_events = [ev for ev in events if ev["event"] == "tool"]
    assert tool_events and tool_events[0]["name"] == "calculator"
    assert tool_events[0]["arguments"] == '{"expression": "17 * 23 + 4"}'

    detail = client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)
    ).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "tool", "assistant"]

    tool_msg = detail["messages"][2]
    assert tool_msg["role"] == "tool"
    assert tool_msg["content"] == "395"
    assert tool_msg["tool_name"] == "calculator"

    assistant_call = detail["messages"][1]
    assert assistant_call["content"] == ""
    assert assistant_call["reasoning"] == "computing"
    calls = json.loads(assistant_call["tool_arguments"])
    assert calls[0]["function"]["name"] == "calculator"
    assert json.loads(calls[0]["function"]["arguments"]) == {"expression": "17 * 23 + 4"}


def test_tool_result_is_fed_back_with_matching_call_id(client, conv):
    token, pid, cid = conv
    llm = ScriptedLLM(
        [
            Msg(tool_calls=[ToolCall("call_xyz", "calculator", '{"expression": "2+2"}')]),
            Msg(content="4"),
        ]
    )
    overrides(client, llm)

    chat_events(client, token, pid, cid, "hi")

    model, messages, tools = llm.calls[1]
    tool_messages = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "call_xyz"
    assert tool_messages[0]["content"] == "4"


def test_chat_history_replays_tool_round_in_next_turn(client, conv):
    token, pid, cid = conv
    llm = ScriptedLLM(
        [
            Msg(tool_calls=[ToolCall("call_1", "calculator", '{"expression": "1+1"}')]),
            Msg(content="2"),
            Msg(content="final"),
        ]
    )
    overrides(client, llm)

    chat_events(client, token, pid, cid, "a")
    chat_events(client, token, pid, cid, "b")

    messages = llm.calls[2][1]
    asst = [m for m in messages if m.get("role") == "assistant" and "tool_calls" in m]
    tool = [m for m in messages if m.get("role") == "tool"]
    assert len(asst) == 1
    assert asst[0]["tool_calls"][0]["id"] == "call_1"
    assert asst[0]["tool_calls"][0]["function"]["name"] == "calculator"
    assert len(tool) == 1
    assert tool[0]["tool_call_id"] == "call_1"
    assert tool[0]["content"] == "2"


def test_chat_with_search_project_files_tool(client, conv):
    token, pid, cid = conv
    payload = "The company plan covers the renegotiation of the Mumbai office lease." * 300
    up = client.post(
        f"/projects/{pid}/files",
        headers=auth_headers(token),
        files={"file": ("plan.txt", payload.encode(), "text/plain")},
    )
    assert up.status_code == 201

    llm = ScriptedLLM(
        [
            Msg(tool_calls=[ToolCall("call_s", "search_project_files", '{"query": "what offices are covered?"}')]),
            Msg(content="based on files."),
        ]
    )
    overrides(client, llm)

    _, events = chat_events(client, token, pid, cid, "hi")
    done = done_event(events)
    assert done is not None
    assert done["content"] == "based on files."

    detail = client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)
    ).json()
    tool_msg = detail["messages"][2]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_name"] == "search_project_files"
    assert "Mumbai" in tool_msg["content"]


def test_chat_loop_stops_after_max_tool_turns(client, conv):
    token, pid, cid = conv
    llm = ScriptedLLM(
        [Msg(tool_calls=[ToolCall("call_x", "calculator", '{"expression": "1"}')])]
    )
    overrides(client, llm)

    _, events = chat_events(client, token, pid, cid, "hi")
    errors = [ev for ev in events if ev["event"] == "error"]
    assert len(errors) == 1
    assert "several tool rounds" in errors[0]["error"]
    assert done_event(events) is None


def test_reasoning_is_streamed_and_persisted_separately_from_content(client, db_session, conv):
    token, pid, cid = conv
    llm = ScriptedLLM(
        [
            Msg(
                tool_calls=[ToolCall("call_r", "calculator", '{"expression": "1+1"}')],
                thinking="REASONING-SECRET",
            ),
            Msg(content="2", thinking="REASONING-SECRET"),
        ]
    )
    overrides(client, llm)

    _, events = chat_events(client, token, pid, cid, "hi")
    # thinking deltas ARE streamed live...
    thinking = [ev for ev in events if ev["event"] == "thinking"]
    assert thinking and thinking[0]["delta"] == "REASONING-SECRET"
    assert done_event(events)["content"] == "2"
    assert done_event(events)["reasoning"] == "REASONING-SECRET"

    # ...and persisted in the reasoning field, never inside content
    rows = sorted(db_session.query(Message).all(), key=lambda m: m.created_at)
    assistants = [r for r in rows if r.role == "assistant"]
    tool_round, final = assistants[0], assistants[1]
    assert tool_round.role == "assistant" and tool_round.reasoning == "REASONING-SECRET"
    assert final.role == "assistant" and final.reasoning == "REASONING-SECRET"
    assert "REASONING" not in (tool_round.content or "")
    assert "REASONING" not in (final.content or "")


def test_tool_call_arguments_not_persisted_in_history(client, db_session, conv):
    token, pid, cid = conv
    llm = ScriptedLLM(
        [Msg(content="plain answer")]
    )
    overrides(client, llm)

    _, events = chat_events(client, token, pid, cid, "hi")
    assert done_event(events)["content"] == "plain answer"

    detail = client.get(
        f"/projects/{pid}/conversations/{cid}", headers=auth_headers(token)
    ).json()
    # No tool involved: exactly two plain messages, no tool remnants.
    assert [(m["role"], m["content"]) for m in detail["messages"]] == [
        ("user", "hi"),
        ("assistant", "plain answer"),
    ]
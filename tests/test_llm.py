import httpx
import openai
import pytest
from types import SimpleNamespace

from app.llm import LLMClient, _is_retryable


def _status_error(status, message):
    cls = {
        400: openai.BadRequestError,
        401: openai.AuthenticationError,
        429: openai.RateLimitError,
        500: openai.InternalServerError,
    }.get(status, openai.APIStatusError)
    return cls(
        message,
        response=httpx.Response(status, request=httpx.Request("POST", "http://primary.test")),
        body=None,
    )


def _ratelimit():
    return _status_error(429, "primary rate-limited")


class _Chunk:
    def __init__(self, content=None, reasoning=None, tool_calls=None, usage=None):
        self.choices = [
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content,
                    reasoning_content=reasoning,
                    reasoning=None,
                    tool_calls=tool_calls,
                )
            )
        ]
        self.usage = usage


class _Stream:
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3)

    def __init__(self, chunks):
        self._chunks = iter(chunks)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._chunks)


class _Completions:
    def __init__(self, create):
        self.create = create


class _Client:
    def __init__(self, create):
        self.chat = SimpleNamespace(completions=_Completions(create))


def _client_with_fallbacks(primary_create, fallback_create):
    llm = LLMClient(api_key="k", base_url="http://primary")
    llm._fallback_api_key = "k2"
    llm._fallback_base_url = "http://fallback"
    llm._fallback_model = "deepseek/deepseek-v4-flash"
    llm._get_client = lambda: _Client(primary_create)
    llm._get_fallback_client = lambda: _Client(fallback_create)
    return llm


def test_is_retryable_only_for_provider_side_conditions():
    assert _is_retryable(_ratelimit()) is True
    assert _is_retryable(_status_error(500, "boom")) is True
    assert _is_retryable(openai.APIConnectionError(request=None)) is True
    assert _is_retryable(_status_error(400, "bad model")) is False
    assert _is_retryable(_status_error(401, "bad key")) is False
    assert _is_retryable(RuntimeError("huh")) is False


def test_stream_falls_back_to_secondary_when_primary_rate_limited(monkeypatch=None):
    called = []

    def primary_create(**kw):
        called.append(("primary", kw["model"]))
        raise _ratelimit()

    def fallback_create(**kw):
        called.append(("fallback", kw["model"]))
        return _Stream(
            [
                _Chunk(reasoning="thinking hard"),
                _Chunk(content="hello"),
                _Chunk(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3)),
            ]
        )

    llm = _client_with_fallbacks(primary_create, fallback_create)
    events = list(llm.stream("deepseek-v4-flash", [{"role": "user", "content": "hi"}]))

    assert [c[0] for c in called] == ["primary", "fallback"]
    assert called[0][1] == "deepseek-v4-flash"
    assert called[1][1] == "deepseek/deepseek-v4-flash"

    thinking = [e["text"] for e in events if e["type"] == "thinking"]
    assert thinking == ["thinking hard"]

    result = events[-1]
    assert result["type"] == "result"
    assert result["provider"] == "fallback"
    assert result["model"] == "deepseek/deepseek-v4-flash"
    assert result["content"] == "hello"
    assert result["usage"].total_tokens == 3


def test_stream_raises_when_no_fallback_configured():
    def primary_create(**kw):
        raise _ratelimit()

    llm = LLMClient(api_key="k", base_url="http://primary")
    llm._fallback_api_key = ""
    llm._get_client = lambda: _Client(primary_create)

    with pytest.raises(openai.RateLimitError):
        list(llm.stream("m", [{"role": "user", "content": "x"}]))


def test_non_retryable_error_is_not_retried_on_fallback():
    called = []

    def primary_create(**kw):
        called.append("primary")
        raise _status_error(400, "bad model")

    def fallback_create(**kw):
        called.append("fallback")
        return _Stream([_Chunk(content="x")])

    llm = _client_with_fallbacks(primary_create, fallback_create)
    with pytest.raises(openai.BadRequestError):
        list(llm.stream("m", [{"role": "user", "content": "x"}]))

    assert called == ["primary"]


def test_stream_aggregates_fragmented_tool_call_deltas():
    def create(**kw):
        return _Stream(
            [
                _Chunk(
                    tool_calls=[
                        SimpleNamespace(index=0, id="call_1", function=SimpleNamespace(name="f", arguments='{"a"'))
                    ]
                ),
                _Chunk(
                    tool_calls=[
                        SimpleNamespace(index=0, id=None, function=SimpleNamespace(name=None, arguments=":1}"))
                    ]
                ),
                _Chunk(),
            ]
        )

    llm = LLMClient(api_key="k", base_url="http://primary")
    llm._fallback_api_key = ""
    llm._get_client = lambda: _Client(create)

    events = list(llm.stream("m", [{"role": "user", "content": "x"}]))
    tool_events = [e for e in events if e["type"] == "tool"]
    assert len(tool_events) == 2
    assert tool_events[-1]["id"] == "call_1"
    assert tool_events[-1]["name"] == "f"
    assert tool_events[-1]["arguments"] == '{"a":1}'

    result = events[-1]
    call = result["tool_calls"][0]
    assert call["id"] == "call_1"
    assert call["function"]["name"] == "f"
    assert call["function"]["arguments"] == '{"a":1}'


def test_stream_sends_nested_reasoning_effort_only_for_max():
    captured = []

    def create(**kw):
        captured.append(kw)
        return _Stream([_Chunk(content="x")])

    llm = LLMClient(api_key="k", base_url="http://primary")
    llm._fallback_api_key = ""
    llm._get_client = lambda: _Client(create)

    list(llm.stream("m", [{"role": "user", "content": "x"}], reasoning_effort="max"))
    list(llm.stream("m", [{"role": "user", "content": "x"}]))
    list(llm.stream("m", [{"role": "user", "content": "x"}], reasoning_effort="standard"))

    assert captured[0]["extra_body"] == {"reasoning": {"effort": "xhigh"}}
    assert "extra_body" not in captured[1]
    assert "extra_body" not in captured[2]


def test_stream_forwards_reasoning_effort_to_fallback():
    captured = []

    def primary_create(**kw):
        raise _ratelimit()

    def fallback_create(**kw):
        captured.append(kw)
        return _Stream([_Chunk(content="x")])

    llm = _client_with_fallbacks(primary_create, fallback_create)
    list(llm.stream("m", [{"role": "user", "content": "x"}], reasoning_effort="max"))

    assert captured[0]["extra_body"] == {"reasoning": {"effort": "xhigh"}}
    assert captured[0]["model"] == "deepseek/deepseek-v4-flash"


def test_complete_sends_nested_reasoning_effort_only_for_max():
    captured = []

    def create(**kw):
        captured.append(kw)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi", tool_calls=None))],
            usage=None,
        )

    llm = LLMClient(api_key="k", base_url="http://primary")
    llm._fallback_api_key = ""
    llm._get_client = lambda: _Client(create)

    llm.complete("m", [{"role": "user", "content": "x"}], reasoning_effort="max")
    llm.complete("m", [{"role": "user", "content": "x"}])

    assert captured[0]["extra_body"] == {"reasoning": {"effort": "xhigh"}}
    assert "extra_body" not in captured[1]
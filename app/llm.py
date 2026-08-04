import json
from typing import Any, Iterator

import openai
from openai import OpenAI

from app.config import settings

MAX_HISTORY_MESSAGES = 50

# Event protocol yielded by LLMClient.stream():
#   {"type": "thinking", "text": str}   live reasoning delta
#   {"type": "content", "text": str}    live answer delta
#   {"type": "tool", "id", "name", "arguments"}  live tool-call progress
#   {"type": "result", "content", "reasoning", "tool_calls": list|None, "usage",
#    "provider": "primary"|"fallback", "model": str}  end of this generation


def _is_retryable(exc: Exception) -> bool:
    """Provider-side conditions we are willing to retry on the fallback:
    rate limits, connection/timeout problems, and 5xx errors. 4xx (bad
    model, auth) are NOT retried — they would fail identically elsewhere."""
    if isinstance(exc, (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError)):
        return True
    if isinstance(exc, openai.APIStatusError) and exc.status_code >= 500:
        return True
    return False


class LLMClient:
    """Thin OpenAI-compatible client (OpenRouter / opencode-go via base_url).

    Supports live streaming of reasoning + content deltas and automatic
    fallback to a secondary provider when the primary fails before yielding
    any tokens (e.g. opencode-go's free-tier 5-hour limit).
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = api_key or settings.openai_api_key
        self._base_url = base_url or settings.openai_base_url
        self._fallback_api_key = settings.openai_fallback_api_key
        self._fallback_base_url = settings.openai_fallback_base_url
        self._fallback_model = settings.openai_fallback_model or settings.default_model
        self._client: OpenAI | None = None
        self._fallback_client: OpenAI | None = None

    @staticmethod
    def _build_client(api_key: str, base_url: str) -> OpenAI:
        return OpenAI(api_key=api_key, base_url=base_url)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = self._build_client(self._api_key, self._base_url)
        return self._client

    def _get_fallback_client(self) -> OpenAI:
        if self._fallback_client is None:
            self._fallback_client = self._build_client(self._fallback_api_key, self._fallback_base_url)
        return self._fallback_client

    def complete(self, model: str, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> Any:
        """Non-streaming completion, kept for compatibility/testing.

        Returns the raw chat message so callers can inspect `content` and
        `tool_calls`. Token usage is attached as a non-standard `message.usage`
        attribute copied from the response.
        """
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        response = self._get_client().chat.completions.create(**kwargs)
        message = response.choices[0].message
        try:
            object.__setattr__(message, "usage", response.usage)
        except Exception:
            pass
        return message

    def stream(self, model: str, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> Iterator[dict[str, Any]]:
        """Yield live events (see module docstring) for one generation pass.

        If the primary provider fails before yielding its first delta (rate
        limit / connection / 5xx) and a fallback is configured, the whole pass
        is retried on the fallback provider with the fallback model id.
        Mid-stream failures are NOT retried (the client has already rendered
        text from the failing provider).
        """
        attempts: list[tuple[OpenAI, str, str]] = [(self._get_client(), model, "primary")]
        if self._fallback_api_key:
            attempts.append((self._get_fallback_client(), self._fallback_model, "fallback"))

        last_exc: Exception | None = None
        for client, attempt_model, provider in attempts:
            try:
                yield from self._stream_with(client, attempt_model, messages, tools, provider)
                return
            except Exception as exc:
                if not _is_retryable(exc):
                    raise
                last_exc = exc
        assert last_exc is not None
        raise last_exc

    def _stream_with(
        self,
        client: OpenAI,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict] | None,
        provider: str,
    ) -> Iterator[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools

        stream = client.chat.completions.create(**kwargs)
        chunks = iter(stream)
        # Pulling the first chunk performs the HTTP request; failures here are
        # retryable by the caller (nothing has been yielded to the user yet).
        try:
            first = next(chunks)
        except StopIteration:
            first = None
        pending = [first] if first is not None else []

        # The provider is now final — announce it before streaming deltas so
        # the UI can badge fallback providers live.
        yield {"type": "provider", "provider": provider, "model": model}

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_slots: dict[int, dict[str, str]] = {}
        usage = None

        for chunk in pending:
            usage = getattr(chunk, "usage", None) or usage
            yield from self._emit_chunk(chunk, content_parts, reasoning_parts, tool_slots)
        for chunk in chunks:
            usage = getattr(chunk, "usage", None) or usage
            yield from self._emit_chunk(chunk, content_parts, reasoning_parts, tool_slots)

        tool_calls = [
            {
                "id": slot["id"],
                "type": "function",
                "function": {"name": slot["name"], "arguments": slot["arguments"] or "{}"},
            }
            for slot in tool_slots.values()
        ] or None
        yield {
            "type": "result",
            "content": "".join(content_parts),
            "reasoning": "".join(reasoning_parts) or None,
            "tool_calls": tool_calls,
            "usage": usage,
            "provider": provider,
            "model": model,
        }

    def _emit_chunk(self, chunk: Any, content_parts: list[str], reasoning_parts: list[str], tool_slots: dict[int, dict[str, str]]) -> Iterator[dict[str, Any]]:
        if not getattr(chunk, "choices", None):
            return
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if reasoning:
            reasoning_parts.append(reasoning)
            yield {"type": "thinking", "text": reasoning}
        content = getattr(delta, "content", None)
        if content:
            content_parts.append(content)
            yield {"type": "content", "text": content}
        tool_calls = getattr(delta, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                slot = tool_slots.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if getattr(tc, "id", None):
                    slot["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn and getattr(fn, "name", None):
                    slot["name"] = fn.name
                if fn and getattr(fn, "arguments", None):
                    slot["arguments"] += fn.arguments
                yield {
                    "type": "tool",
                    "id": slot["id"],
                    "name": slot["name"],
                    "arguments": slot["arguments"],
                }


def build_chat_messages(
    system_prompt: str, history: list[Any], user_message: str
) -> list[dict[str, Any]]:
    """Reconstruct the OpenAI message list from persisted Message rows.

    Assistant tool-call turns are stored as an assistant message with the full
    `tool_calls` array in `tool_arguments`; each result is a separate
    role="tool" message tied to it by tool_call_id — replay them accordingly.
    """
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for msg in history[-MAX_HISTORY_MESSAGES:]:
        if msg.role == "tool":
            messages.append(
                {"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content}
            )
        elif msg.role == "assistant" and msg.tool_arguments:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": json.loads(msg.tool_arguments),
                }
            )
        else:
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def get_llm_client() -> LLMClient:
    return LLMClient()

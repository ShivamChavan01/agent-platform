from typing import Any

import json

from openai import OpenAI

from app.config import settings

MAX_HISTORY_MESSAGES = 50


class LLMClient:
    """Thin OpenAI-compatible client (OpenRouter via base_url)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = api_key or settings.openai_api_key
        self._base_url = base_url or settings.openai_base_url
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def complete(self, model: str, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> Any:
        """Return the raw chat message so callers can inspect tool_calls.

        The caller reads `message.content` (assistant text) and
        `message.tool_calls` (list of function calls). Persistence must only
        ever store `content` — never a stray `reasoning_content` field.
        """
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        response = self._get_client().chat.completions.create(**kwargs)
        return response.choices[0].message


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

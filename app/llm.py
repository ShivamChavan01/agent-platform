from typing import Any

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

    def complete(self, model: str, messages: list[dict[str, str]]) -> str:
        response = self._get_client().chat.completions.create(
            model=model, messages=messages
        )
        return response.choices[0].message.content or ""


def build_chat_messages(system_prompt: str, history: list[Any], user_message: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for msg in history[-MAX_HISTORY_MESSAGES:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def get_llm_client() -> LLMClient:
    return LLMClient()

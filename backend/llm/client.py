import json
from dataclasses import dataclass
from typing import Any

import httpx

from backend.llm.errors import (
    LLMConfigurationError,
    LLMProviderError,
    LLMResponseError,
)


@dataclass(frozen=True, slots=True)
class ChatCompletion:
    content: str
    data: dict[str, Any]
    model: str
    completion_id: str | None
    usage: dict[str, Any]


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._transport = transport

    async def complete_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> ChatCompletion:
        if not self._api_key:
            raise LLMConfigurationError(
                "LLM_API_KEY is not configured on the backend"
            )
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.HTTPError as error:
            raise LLMProviderError("Unable to reach the configured LLM provider") from error
        if not response.is_success:
            raise LLMProviderError(
                f"LLM provider returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
            choice = body["choices"][0]
            content = choice["message"]["content"]
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict)
                )
            if not isinstance(content, str) or not content.strip():
                raise KeyError("content")
            data = self.parse_json(content)
        except (ValueError, TypeError, KeyError, IndexError) as error:
            raise LLMResponseError("LLM returned an invalid chat completion") from error
        return ChatCompletion(
            content=content,
            data=data,
            model=str(body.get("model") or model),
            completion_id=body.get("id"),
            usage=body.get("usage") if isinstance(body.get("usage"), dict) else {},
        )

    @staticmethod
    def parse_json(content: str) -> dict[str, Any]:
        value = content.strip()
        if value.startswith("```"):
            lines = value.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            value = "\n".join(lines).strip()
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise LLMResponseError("LLM JSON output must be an object")
        return parsed

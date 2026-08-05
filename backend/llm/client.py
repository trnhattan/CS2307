import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

import httpx
from openai import APIStatusError, AsyncOpenAI, OpenAIError

from backend.core.config import Settings
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
    reasoning_details: list[dict[str, Any]]


class LLMClient(Protocol):
    async def complete_json(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
        reasoning_enabled: bool = True,
        web_search_enabled: bool = False,
        web_search_max_results: int = 3,
        provider: str | None = None,
    ) -> ChatCompletion: ...

    async def complete_json_with_tools(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        max_tokens: int,
        temperature: float,
        reasoning_enabled: bool = True,
        max_tool_rounds: int = 4,
        web_search_enabled: bool = False,
        web_search_max_results: int = 3,
        provider: str | None = None,
    ) -> ChatCompletion: ...


class _OpenAICompatibleClient:
    provider_name = "LLM provider"
    api_key_environment_name = "LLM_API_KEY"
    supports_web_search = False

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        timeout_seconds: float,
        http_referer: str | None = None,
        app_title: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._http_referer = http_referer
        self._app_title = app_title
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @property
    def endpoint(self) -> str:
        return self._base_url

    def _headers(self) -> dict[str, str]:
        return {}

    def _extra_body(
        self,
        *,
        reasoning_enabled: bool,
        web_search_enabled: bool,
        web_search_max_results: int,
    ) -> dict[str, Any]:
        return {}

    def _tool_request_options(
        self,
        *,
        tools: list[dict[str, Any]],
        reasoning_enabled: bool,
        web_search_enabled: bool,
        web_search_max_results: int,
    ) -> dict[str, Any]:
        return {
            "tools": tools,
            "tool_choice": "auto",
            "extra_body": self._extra_body(
                reasoning_enabled=reasoning_enabled,
                web_search_enabled=web_search_enabled,
                web_search_max_results=web_search_max_results,
            ),
        }

    def _assert_configured(self) -> None:
        if not self._api_key:
            raise LLMConfigurationError(
                f"{self.api_key_environment_name} is not configured on the backend"
            )

    def _new_client(self) -> AsyncOpenAI:
        http_client = httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        )
        return AsyncOpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout,
            default_headers=self._headers(),
            http_client=http_client,
        )

    async def complete_json(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
        reasoning_enabled: bool = True,
        web_search_enabled: bool = False,
        web_search_max_results: int = 3,
        provider: str | None = None,
    ) -> ChatCompletion:
        self._assert_configured()
        client = self._new_client()
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False,
                response_format={"type": "json_object"},
                extra_body=self._extra_body(
                    reasoning_enabled=reasoning_enabled,
                    web_search_enabled=web_search_enabled,
                    web_search_max_results=web_search_max_results,
                ),
            )
        except APIStatusError as error:
            raise LLMProviderError(
                f"{self.provider_name} returned HTTP {error.status_code}"
            ) from error
        except OpenAIError as error:
            raise LLMProviderError(f"Unable to reach {self.provider_name}") from error
        finally:
            await client.close()
        return self._parse_completion(response, model)

    async def complete_json_with_tools(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        max_tokens: int,
        temperature: float,
        reasoning_enabled: bool = True,
        max_tool_rounds: int = 4,
        web_search_enabled: bool = False,
        web_search_max_results: int = 3,
        provider: str | None = None,
    ) -> ChatCompletion:
        self._assert_configured()
        client = self._new_client()
        conversation = [dict(message) for message in messages]
        try:
            for round_index in range(max_tool_rounds + 1):
                response = await client.chat.completions.create(
                    model=model,
                    messages=conversation,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False,
                    response_format={"type": "json_object"},
                    **self._tool_request_options(
                        tools=tools,
                        reasoning_enabled=reasoning_enabled,
                        web_search_enabled=web_search_enabled,
                        web_search_max_results=web_search_max_results,
                    ),
                )
                choice = response.choices[0]
                message = choice.message
                message_payload = message.model_dump(mode="json", exclude_none=True)
                tool_calls = message_payload.get("tool_calls") or []
                if not tool_calls:
                    return self._parse_completion(response, model, message_payload)
                if round_index >= max_tool_rounds:
                    raise LLMResponseError(
                        f"{self.provider_name} exceeded the learner-tool round limit"
                    )
                conversation.append(message_payload)
                for call in tool_calls:
                    function = call.get("function") or {}
                    name = str(function.get("name") or "")
                    try:
                        arguments = json.loads(function.get("arguments") or "{}")
                    except json.JSONDecodeError as error:
                        raise LLMResponseError(
                            f"{self.provider_name} returned invalid learner-tool arguments"
                        ) from error
                    if not isinstance(arguments, dict):
                        raise LLMResponseError("Learner-tool arguments must be an object")
                    result = await tool_executor(name, arguments)
                    conversation.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "name": name,
                            "content": json.dumps(
                                result,
                                ensure_ascii=False,
                                default=str,
                                separators=(",", ":"),
                            ),
                        }
                    )
        except APIStatusError as error:
            raise LLMProviderError(
                f"{self.provider_name} returned HTTP {error.status_code}"
            ) from error
        except OpenAIError as error:
            raise LLMProviderError(f"Unable to reach {self.provider_name}") from error
        finally:
            await client.close()
        raise LLMResponseError(f"{self.provider_name} did not produce a final response")

    def _parse_completion(
        self,
        response: Any,
        model: str,
        message_payload: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        try:
            choice = response.choices[0]
            message = choice.message
            content = message.content
            if not isinstance(content, str) or not content.strip():
                raise KeyError("content")
            data = self.parse_json(content)
            payload = message_payload or message.model_dump(mode="json")
            reasoning_details = payload.get("reasoning_details") or []
            if not isinstance(reasoning_details, list):
                reasoning_details = []
        except (ValueError, TypeError, KeyError, IndexError) as error:
            raise LLMResponseError(
                f"{self.provider_name} returned an invalid chat completion"
            ) from error
        return ChatCompletion(
            content=content,
            data=data,
            model=str(response.model or model),
            completion_id=response.id,
            usage=(
                {
                    key: value
                    for key, value in response.usage.model_dump(mode="json").items()
                    if value is not None
                }
                if response.usage is not None
                else {}
            ),
            reasoning_details=reasoning_details,
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


class OpenRouterClient(_OpenAICompatibleClient):
    provider_name = "OpenRouter"
    api_key_environment_name = "OPENROUTER_API_KEY"
    supports_web_search = True

    def _headers(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "HTTP-Referer": self._http_referer,
                "X-OpenRouter-Title": self._app_title,
            }.items()
            if value
        }

    def _extra_body(
        self,
        *,
        reasoning_enabled: bool,
        web_search_enabled: bool,
        web_search_max_results: int,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"reasoning": {"enabled": reasoning_enabled}}
        if web_search_enabled:
            body["tools"] = [self._web_search_tool(web_search_max_results)]
        return body

    def _tool_request_options(
        self,
        *,
        tools: list[dict[str, Any]],
        reasoning_enabled: bool,
        web_search_enabled: bool,
        web_search_max_results: int,
    ) -> dict[str, Any]:
        request_tools = list(tools)
        if web_search_enabled:
            request_tools.append(self._web_search_tool(web_search_max_results))
        return {
            "extra_body": {
                "reasoning": {"enabled": reasoning_enabled},
                "tools": request_tools,
                "tool_choice": "auto",
            }
        }

    @staticmethod
    def _web_search_tool(max_results: int) -> dict[str, Any]:
        return {
            "type": "openrouter:web_search",
            "max_total_results": max(1, min(max_results, 10)),
            "search_context_size": "low",
        }


class GeminiClient(_OpenAICompatibleClient):
    provider_name = "Gemini"
    api_key_environment_name = "GEMINI_API_KEY"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        timeout_seconds: float,
        thinking_level: str = "low",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )
        self._thinking_level = thinking_level

    def _extra_body(
        self,
        *,
        reasoning_enabled: bool,
        web_search_enabled: bool,
        web_search_max_results: int,
    ) -> dict[str, Any]:
        if not reasoning_enabled:
            return {}
        return {
            "google": {
                "thinking_config": {
                    "thinking_level": self._thinking_level,
                }
            }
        }


class MultiProviderClient:
    """Routes database-selected models without exposing provider credentials to sys_props."""

    def __init__(self, settings: Settings) -> None:
        self._openrouter = OpenRouterClient(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
            http_referer=settings.openrouter_http_referer,
            app_title=settings.openrouter_app_title,
        )
        self._gemini = GeminiClient(
            base_url=settings.gemini_base_url,
            api_key=settings.gemini_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
            thinking_level=settings.gemini_thinking_level,
        )

    @staticmethod
    def is_gemini_model(model: str) -> bool:
        return model.strip().lower().startswith("gemini-")

    def _client_for(
        self, model: str, provider: str | None = None
    ) -> _OpenAICompatibleClient:
        if provider is None:
            return self._gemini if self.is_gemini_model(model) else self._openrouter
        if provider == "gemini":
            return self._gemini
        if provider == "openrouter":
            return self._openrouter
        raise LLMConfigurationError("LLM_PROVIDER must be openrouter or gemini")

    def is_configured(self, model: str, provider: str | None = None) -> bool:
        return self._client_for(model, provider).configured

    def configuration_message(self, model: str, provider: str | None = None) -> str:
        client = self._client_for(model, provider)
        return f"{client.api_key_environment_name} is not configured"

    def provider_endpoint(self, model: str, provider: str | None = None) -> str:
        return self._client_for(model, provider).endpoint

    async def complete_json(self, **kwargs: Any) -> ChatCompletion:
        model = str(kwargs["model"])
        provider = kwargs.pop("provider", None)
        return await self._client_for(model, provider).complete_json(**kwargs)

    async def complete_json_with_tools(self, **kwargs: Any) -> ChatCompletion:
        model = str(kwargs["model"])
        provider = kwargs.pop("provider", None)
        return await self._client_for(model, provider).complete_json_with_tools(**kwargs)


def create_llm_client(settings: Settings) -> MultiProviderClient:
    return MultiProviderClient(settings)


OpenAICompatibleClient = OpenRouterClient

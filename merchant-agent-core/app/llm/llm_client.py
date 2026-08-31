from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.config.settings import LLMProvider, Settings

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    """One turn in the conversation handed to the LLM."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: Optional[str] = None


@dataclass
class LLMResponse:
    """Raw model output. The Planner - not this module - turns this into a
    structured Decision."""

    content: str
    raw: dict[str, Any] = field(default_factory=dict)


class LLMUnavailableError(Exception):
    """The configured LLM provider could not be reached or returned an error."""


class LLMTimeoutError(LLMUnavailableError):
    """The configured LLM provider did not respond within TOOL_TIMEOUT_SECONDS."""


class LLMClient(ABC):
    """Provider-independent contract for asking a model to reason about the
    next action.

    Implementations only talk to their specific LLM provider - no
    agent-loop, planning, or tool-execution logic belongs here. Swapping
    providers means adding a new LLMClient implementation, never touching
    the agent loop/planner.
    """

    @abstractmethod
    def generate(self, messages: list[LLMMessage], tools: Optional[list[dict[str, Any]]] = None) -> LLMResponse:
        """Ask the model for its next output given the conversation so far
        and the tool definitions currently available."""
        raise NotImplementedError


class FallbackLLMClient(LLMClient):
    """Try a primary provider and fail over to a secondary provider."""

    def __init__(self, primary: LLMClient, secondary: LLMClient):
        self._primary = primary
        self._secondary = secondary

    def generate(self, messages: list[LLMMessage], tools: Optional[list[dict[str, Any]]] = None) -> LLMResponse:
        try:
            return self._primary.generate(messages, tools)
        except (LLMUnavailableError, LLMTimeoutError) as exc:
            logger.warning("Primary LLM failed; falling back to secondary provider: %s", exc)
            return self._secondary.generate(messages, tools)


class EchoLLMClient(LLMClient):
    """Deterministic, network-free LLMClient used when no LLM_API_KEY is
    configured AND no provider is explicitly set. Lets the rest of the
    service run locally/in CI without a real provider. NOT suitable for
    production use - it never actually reasons about tool calls."""

    def generate(self, messages: list[LLMMessage], tools: Optional[list[dict[str, Any]]] = None) -> LLMResponse:
        last_user_message = next((m for m in reversed(messages) if m.role == "user"), None)
        content = (
            '{"action": "FINAL_RESPONSE", "response": '
            '"No LLM provider is configured (LLM_API_KEY is empty), so I could not process: '
            f'{(last_user_message.content if last_user_message else "")!r}."}}'
        )
        return LLMResponse(content=content, raw={"provider": "echo"})


class OpenAIChatLLMClient(LLMClient):
    """Minimal OpenAI-compatible Chat Completions client built directly on
    httpx (a dependency this service already has), so we don't need to add
    the full `openai` SDK just for this. Implement LLMClient again for any
    other provider - the agent loop never depends on this class directly.
    """

    def __init__(self, settings: Settings, client: Optional[httpx.Client] = None):
        self._model = settings.llm_model
        self._api_key = settings.llm_api_key
        self._max_tokens = settings.llm_max_output_tokens
        base_url = settings.llm_base_url or "https://api.groq.com/openai/v1"
        self._client = client or httpx.Client(
            base_url=base_url, timeout=settings.tool_timeout_seconds
        )

    def generate(self, messages: list[LLMMessage], tools: Optional[list[dict[str, Any]]] = None) -> LLMResponse:
        openai_messages = [self._to_openai_message(m) for m in messages]
        if openai_messages and openai_messages[-1]["role"] == "assistant":
            openai_messages.append({"role": "user", "content": "Continue."})
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
        }


        try:
            response = self._client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
        except httpx.TimeoutException as exc:
            logger.error("Timed out waiting for the LLM provider")
            raise LLMTimeoutError("Timed out waiting for the LLM provider") from exc
        except httpx.RequestError as exc:
            logger.error("Could not reach the LLM provider: %s", exc)
            raise LLMUnavailableError(f"Could not reach the LLM provider: {exc}") from exc

        if response.status_code >= 400:
            logger.error("LLM provider returned HTTP %d: %s", response.status_code, response.text)
            raise LLMUnavailableError(f"LLM provider returned {response.status_code}: {response.text[:200]}")

        # Extract the model's textual reply
        body = response.json()
        try:
            content = body["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Malformed response body from LLM provider")
            raise LLMUnavailableError("Malformed response from LLM provider") from exc

        logger.debug("Raw LLM content: %r", content)

        # The model may wrap its reply in markdown fences (e.g. ```json ... ```).
        # Remove them so the planner receives clean JSON.
        if content.startswith("```"):
            # Strip leading/trailing backticks and possible language tag.
            lines = content.splitlines()
            # Remove the first line if it looks like a fence with optional language.
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            # Remove the last line if it is a closing fence.
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        return LLMResponse(content=content, raw=body)



    @staticmethod
    def _to_openai_message(message: LLMMessage) -> dict[str, Any]:
        # The agent uses text-based JSON decisions (not native tool-call protocol).
        # Groq's API requires tool_call_id for role=tool messages, which we don't have.
        # Convert tool-result messages to user messages so the history stays valid.
        role = message.role
        content = message.content
        if role == "tool":
            role = "user"
            content = f"[Tool result]\n{content}"
        entry: dict[str, Any] = {"role": role, "content": content}
        if message.name and role != "user":
            entry["name"] = message.name
        return entry


def create_llm_client(settings: Settings) -> LLMClient:
    """Factory that picks an LLMClient implementation from configuration.
    This is the one place that needs to change to add a new provider.

    Provider resolution order:
      1. LLM_PROVIDER=huggingface  → HuggingFaceLLMClient (free, no token needed)
         If GEMINI_API_KEY is set, auto-fallback to Gemini when HF is unavailable.
      2. LLM_PROVIDER=gemini       → GeminiLLMClient (requires GEMINI_API_KEY)
      3. LLM_PROVIDER=openai       → OpenAIChatLLMClient (requires LLM_API_KEY)
      4. No matching key set       → EchoLLMClient (dev/CI fallback)
    """
    # Import here to avoid a circular import on the HuggingFace module.
    from app.llm.gemini_llm_client import GeminiLLMClient  # noqa: PLC0415
    from app.llm.huggingface_llm_client import HuggingFaceLLMClient  # noqa: PLC0415

    if settings.llm_provider == LLMProvider.HUGGINGFACE:
        logger.info(
            "Using HuggingFaceLLMClient: model=%s (anonymous free tier; set LLM_API_KEY for higher rate limits)",
            settings.llm_model,
        )
        primary = HuggingFaceLLMClient(settings)
        if settings.gemini_api_key:
            logger.info("Gemini fallback is enabled for HuggingFace provider")
            return FallbackLLMClient(primary=primary, secondary=GeminiLLMClient(settings))
        return primary

    if settings.llm_provider == LLMProvider.GEMINI:
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY is not set - using EchoLLMClient (local/dev only, not a real LLM)")
            return EchoLLMClient()
        return GeminiLLMClient(settings)

    if settings.llm_provider == LLMProvider.OPENAI:
        if not settings.llm_api_key:
            logger.warning("LLM_API_KEY is not set - using EchoLLMClient (local/dev only, not a real LLM)")
            return EchoLLMClient()
        return OpenAIChatLLMClient(settings)

    if not settings.llm_api_key and not settings.gemini_api_key:
        logger.warning("No LLM API key is set - using EchoLLMClient (local/dev only, not a real LLM)")
        return EchoLLMClient()

    raise NotImplementedError(
        f"No LLMClient implementation is registered for provider '{settings.llm_provider.value}'. "
        "Implement LLMClient for this provider and wire it up in create_llm_client()."
    )


from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from app.config.settings import Settings
from app.llm.llm_client import LLMClient, LLMMessage, LLMResponse, LLMUnavailableError, LLMTimeoutError

logger = logging.getLogger(__name__)

# HuggingFace models known to work well with the free Inference API and to
# produce structured JSON decisions reliably when asked via a clear system prompt.
# Using HuggingFaceH4/zephyr-7b-beta: instruction-tuned, JSON-friendly, no token
# required on the free public inference tier.
_DEFAULT_MODEL = "HuggingFaceH4/zephyr-7b-beta"

# HuggingFace Inference API uses an OpenAI-compatible chat endpoint:
#   POST https://api-inference.huggingface.co/models/{model}/v1/chat/completions
# Requests without an Authorization header work for public models (free tier,
# rate-limited). Providing an HF_TOKEN speeds things up but is never required.
_HF_BASE = "https://api-inference.huggingface.co"


class HuggingFaceLLMClient(LLMClient):
    """LLM client that calls the HuggingFace Inference API's OpenAI-compatible
    chat completions endpoint.

    No API token is required - the free public tier works anonymously, though
    it is rate-limited. If LLM_API_KEY is set in the environment, it will be
    sent as an Authorization Bearer token to bypass rate limits.

    The model is controlled by LLM_MODEL (default: HuggingFaceH4/zephyr-7b-beta).
    Any HF model that supports the Messages API can be used.
    """

    def __init__(self, settings: Settings, client: Optional[httpx.Client] = None):
        self._model = settings.llm_model or _DEFAULT_MODEL
        self._api_key = settings.llm_api_key  # may be empty - that's fine
        self._max_output_tokens = max(64, settings.llm_max_output_tokens)
        base_url = (settings.llm_base_url or _HF_BASE).rstrip("/")
        self._endpoint = f"{base_url}/models/{self._model}/v1/chat/completions"
        self._client = client or httpx.Client(timeout=settings.tool_timeout_seconds)
        logger.info(
            "HuggingFaceLLMClient initialised: model=%s, authenticated=%s",
            self._model,
            bool(self._api_key),
        )

    def generate(self, messages: list[LLMMessage], tools: Optional[list[dict[str, Any]]] = None) -> LLMResponse:
        """Send the conversation to HuggingFace and return the model's text.

        We ask the model for a JSON decision via the system prompt (managed by
        PromptManager/Planner) - HF models don't natively support OpenAI-style
        tool_choice, so we rely on the structured prompt + JSON parsing in
        Planner._parse_decision() instead.
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [self._to_hf_message(m) for m in messages],
            "max_new_tokens": self._max_output_tokens,
            "temperature": 0.1,  # low temperature for reliable JSON output
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        logger.debug("Calling HuggingFace Inference API: model=%s", self._model)

        try:
            response = self._client.post(self._endpoint, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            logger.error("Timed out waiting for HuggingFace Inference API")
            raise LLMTimeoutError("Timed out waiting for the HuggingFace Inference API") from exc
        except httpx.RequestError as exc:
            logger.error("Could not reach HuggingFace Inference API: %s", exc)
            raise LLMUnavailableError(f"Could not reach HuggingFace Inference API: {exc}") from exc

        if response.status_code == 503:
            # HuggingFace returns 503 when the model is loading (cold start).
            logger.warning(
                "HuggingFace model '%s' is loading (503). "
                "Wait a few seconds and retry, or use a pre-warmed model.",
                self._model,
            )
            raise LLMUnavailableError(
                f"HuggingFace model '{self._model}' is currently loading. Please retry in a few seconds."
            )

        if response.status_code == 429:
            logger.warning("HuggingFace Inference API rate limit hit (429). Set LLM_API_KEY to get higher limits.")
            raise LLMUnavailableError(
                "HuggingFace Inference API rate limit exceeded. "
                "Set LLM_API_KEY to a free HuggingFace token to increase your quota."
            )

        if response.status_code >= 400:
            logger.error("HuggingFace Inference API returned HTTP %d: %s", response.status_code, response.text[:200])
            raise LLMUnavailableError(
                f"HuggingFace Inference API returned {response.status_code}: {response.text[:200]}"
            )

        body = response.json()

        # Parse OpenAI-compatible chat completions response shape:
        #   { "choices": [{ "message": { "content": "..." } }] }
        try:
            content = body["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected HuggingFace response shape: %s", body)
            raise LLMUnavailableError("Malformed response from HuggingFace Inference API") from exc

        # Strip any accidental markdown fences the model may have added.
        content = _strip_fences(content).strip()
        logger.debug("HuggingFace raw content: %.200s", content)
        return LLMResponse(content=content, raw=body)

    @staticmethod
    def _to_hf_message(message: LLMMessage) -> dict[str, Any]:
        """Convert an LLMMessage to the HuggingFace/OpenAI message dict.

        HF's Messages API uses the same role names as OpenAI (system, user,
        assistant). The 'tool' role is mapped to 'user' with a prefix so the
        model sees tool results as part of the conversation.
        """
        if message.role == "tool":
            # HF models don't natively have a 'tool' role; embed it as a
            # user message so the model can observe the tool's outcome.
            return {"role": "user", "content": f"[Tool Result] {message.content}"}
        return {"role": message.role, "content": message.content}


def _strip_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences that some models emit."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Drop the opening fence line and the closing fence line (if present).
        inner = lines[1:]
        if inner and inner[-1].strip().startswith("```"):
            inner = inner[:-1]
        return "\n".join(inner)
    return stripped

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config.settings import Settings
from app.llm.llm_client import LLMClient, LLMMessage, LLMResponse, LLMUnavailableError, LLMTimeoutError

logger = logging.getLogger(__name__)

_DEFAULT_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"


class GeminiLLMClient(LLMClient):
    """LLM client for Gemini's generateContent endpoint.

    This client keeps prompts compact and uses low output token limits to reduce
    usage and cost while preserving structured decision output quality.
    """

    def __init__(self, settings: Settings, client: Optional[httpx.Client] = None):
        self._api_key = (settings.gemini_api_key or settings.llm_api_key).strip()
        self._endpoint = (settings.gemini_base_url or _DEFAULT_GEMINI_BASE).strip().strip('"')
        self._fallback_endpoint = (settings.gemini_fallback_base_url or "").strip().strip('"')
        self._max_output_tokens = max(64, settings.llm_max_output_tokens)
        self._client = client or httpx.Client(timeout=settings.tool_timeout_seconds)

    def generate(self, messages: list[LLMMessage], tools: Optional[list[dict[str, Any]]] = None) -> LLMResponse:
        if not self._api_key:
            raise LLMUnavailableError("Gemini API key is not configured. Set GEMINI_API_KEY.")

        payload: dict[str, Any] = {
            "contents": [self._to_gemini_content(m) for m in messages],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": self._max_output_tokens,
                "topP": 0.8,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

        try:
            response = self._client.post(self._endpoint, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            logger.error("Timed out waiting for Gemini API")
            raise LLMTimeoutError("Timed out waiting for Gemini API") from exc
        except httpx.RequestError as exc:
            logger.error("Could not reach Gemini API: %s", exc)
            raise LLMUnavailableError(f"Could not reach Gemini API: {exc}") from exc

        primary_503_text = response.text if response.status_code == 503 else ""
        if response.status_code == 503 and self._fallback_endpoint and self._fallback_endpoint != self._endpoint:
            logger.warning("Gemini primary endpoint unavailable (503). Retrying with fallback endpoint.")
            try:
                response = self._client.post(self._fallback_endpoint, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                logger.error("Timed out waiting for Gemini fallback endpoint")
                raise LLMTimeoutError("Timed out waiting for Gemini fallback endpoint") from exc
            except httpx.RequestError as exc:
                logger.error("Could not reach Gemini fallback endpoint: %s", exc)
                raise LLMUnavailableError(f"Could not reach Gemini fallback endpoint: {exc}") from exc

            if response.status_code >= 400 and primary_503_text:
                logger.error("Gemini fallback endpoint failed; preserving primary 503 response")
                raise LLMUnavailableError(f"Gemini API returned 503: {primary_503_text[:200]}")

        if response.status_code >= 400:
            logger.error("Gemini API returned HTTP %d: %s", response.status_code, response.text[:200])
            raise LLMUnavailableError(f"Gemini API returned {response.status_code}: {response.text[:200]}")

        body = response.json()
        content = self._extract_text(body)
        return LLMResponse(content=content.strip(), raw=body)

    @staticmethod
    def _to_gemini_content(message: LLMMessage) -> dict[str, Any]:
        if message.role == "assistant":
            role = "model"
            text = message.content
        elif message.role == "system":
            role = "user"
            text = f"[System Instruction]\n{message.content}"
        elif message.role == "tool":
            role = "user"
            text = f"[Tool Result]\n{message.content}"
        else:
            role = "user"
            text = message.content
        return {"role": role, "parts": [{"text": text}]}

    @staticmethod
    def _extract_text(body: dict[str, Any]) -> str:
        candidates = body.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise LLMUnavailableError("Malformed response from Gemini API")

        first = candidates[0]
        content = first.get("content", {})
        parts = content.get("parts", [])
        if not isinstance(parts, list) or not parts:
            raise LLMUnavailableError("Malformed response from Gemini API")

        text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
        text = "\n".join(tp for tp in text_parts if tp)
        if not text:
            raise LLMUnavailableError("Gemini response did not contain text output")
        return text

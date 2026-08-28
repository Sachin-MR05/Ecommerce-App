from __future__ import annotations

import time
from typing import Any, Callable, Optional

from app.llm.llm_client import LLMClient, LLMMessage, LLMResponse


class TimingLLMClient(LLMClient):
    """Wraps any LLMClient to report call latency to `on_latency`, without
    changing behavior, retries, or fallback logic at all.

    Deliberately a decorator, not an edit to OpenAIChatLLMClient/
    GeminiLLMClient/HuggingFaceLLMClient/FallbackLLMClient - instrumenting
    every provider implementation individually would mean touching four
    files for one cross-cutting concern. Wrapping create_llm_client()'s
    return value once (see main.py) covers all of them, including
    FallbackLLMClient's primary/secondary retry - the reported latency is
    for the full generate() call as the agent loop actually experiences it,
    successful fallback included.

    On failure, still reports the elapsed time before re-raising - a slow
    failing call is exactly the kind of thing a performance/latency panel
    should surface, not hide.
    """

    def __init__(self, inner: LLMClient, on_latency: Callable[[float], None]):
        self._inner = inner
        self._on_latency = on_latency

    def generate(self, messages: list[LLMMessage], tools: Optional[list[dict[str, Any]]] = None) -> LLMResponse:
        start = time.perf_counter()
        try:
            return self._inner.generate(messages, tools)
        finally:
            self._on_latency((time.perf_counter() - start) * 1000)

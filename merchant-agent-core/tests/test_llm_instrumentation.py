from __future__ import annotations

import pytest

from app.llm.llm_client import LLMClient, LLMMessage, LLMResponse
from monitoring.llm_instrumentation import TimingLLMClient


class _StubLLMClient(LLMClient):
    def __init__(self, response: LLMResponse = None, error: Exception = None):
        self._response = response or LLMResponse(content="ok")
        self._error = error

    def generate(self, messages, tools=None):
        if self._error:
            raise self._error
        return self._response


def test_timing_llm_client_reports_latency_and_forwards_response():
    latencies = []
    inner = _StubLLMClient(response=LLMResponse(content="hello"))
    client = TimingLLMClient(inner, on_latency=latencies.append)

    result = client.generate([LLMMessage(role="user", content="hi")])

    assert result.content == "hello"
    assert len(latencies) == 1
    assert latencies[0] >= 0.0


def test_timing_llm_client_reports_latency_even_when_generate_raises():
    latencies = []
    inner = _StubLLMClient(error=RuntimeError("boom"))
    client = TimingLLMClient(inner, on_latency=latencies.append)

    with pytest.raises(RuntimeError):
        client.generate([LLMMessage(role="user", content="hi")])

    assert len(latencies) == 1


def test_monitoring_store_surfaces_llm_latency_average():
    from monitoring.store import MonitoringStore

    store = MonitoringStore()
    store.record_llm_latency(100.0)
    store.record_llm_latency(200.0)

    performance = store.performance_metrics()
    assert performance.llm_latency_ms == 150.0

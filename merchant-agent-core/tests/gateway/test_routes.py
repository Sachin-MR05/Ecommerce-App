import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent.orchestrator import AgentOrchestrator
from app.contracts.agent_request import AgentRequest
from app.contracts.agent_response import AgentResponse
from app.gateway import routes as gateway_routes
from app.gateway.authentication import AuthenticationError, AuthenticationService
from app.gateway.error_handlers import register_gateway_error_handlers
from app.gateway.middleware import RequestLoggingMiddleware
from app.gateway.rate_limiter import RateLimiter


class ScriptedOrchestrator(AgentOrchestrator):
    """Test double: returns a pre-scripted AgentResponse, or raises to
    simulate an unexpected Agent Core failure."""

    def __init__(self, response: AgentResponse | None = None, raise_error: Exception | None = None):
        self._response = response
        self._raise_error = raise_error
        self.received_requests: list[AgentRequest] = []

    def process(self, request: AgentRequest) -> AgentResponse:
        self.received_requests.append(request)
        if self._raise_error is not None:
            raise self._raise_error
        assert self._response is not None
        return self._response


class AlwaysAllowAuth(AuthenticationService):
    def authenticate(self, authorization, user_id) -> str:
        return user_id or "anonymous"


class AlwaysDenyAuth(AuthenticationService):
    def authenticate(self, authorization, user_id) -> str:
        raise AuthenticationError("invalid credentials")


class AlwaysAllowRateLimiter(RateLimiter):
    def allow(self, user_id: str) -> bool:
        return True


class AlwaysDenyRateLimiter(RateLimiter):
    def allow(self, user_id: str) -> bool:
        return False


def _build_app(orchestrator, auth_service=None, rate_limiter=None) -> FastAPI:
    app = FastAPI()
    app.include_router(gateway_routes.router)
    app.dependency_overrides[gateway_routes.get_agent_orchestrator] = lambda: orchestrator
    app.dependency_overrides[gateway_routes.get_authentication_service] = lambda: (
        auth_service or AlwaysAllowAuth()
    )
    app.dependency_overrides[gateway_routes.get_rate_limiter] = lambda: (rate_limiter or AlwaysAllowRateLimiter())
    app.add_middleware(RequestLoggingMiddleware)
    register_gateway_error_handlers(app)
    return app


VALID_PAYLOAD = {
    "sessionId": "session-001",
    "userId": "user-001",
    "message": "I want to buy 2 iPhones",
    "channel": "web",
}


def test_valid_request_returns_200():
    scripted = AgentResponse.success(request_id="placeholder", message="I found 2 iPhones. Proceed?")
    orchestrator = ScriptedOrchestrator(response=scripted)
    client = TestClient(_build_app(orchestrator))

    resp = client.post("/agent/message", json=VALID_PAYLOAD, headers={"Authorization": "Bearer dev-token"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert body["message"] == "I found 2 iPhones. Proceed?"
    assert "requestId" in body and body["requestId"]


def test_empty_message_returns_400():
    orchestrator = ScriptedOrchestrator(response=AgentResponse.success("x", "unused"))
    client = TestClient(_build_app(orchestrator))

    payload = {**VALID_PAYLOAD, "message": ""}
    resp = client.post("/agent/message", json=payload, headers={"Authorization": "Bearer dev-token"})

    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["error"]["code"] == "EMPTY_MESSAGE"
    assert not orchestrator.received_requests  # never reached the orchestrator


def test_missing_session_id_returns_400():
    orchestrator = ScriptedOrchestrator(response=AgentResponse.success("x", "unused"))
    client = TestClient(_build_app(orchestrator))

    payload = {"userId": "user-001", "message": "hello", "channel": "web"}
    resp = client.post("/agent/message", json=payload, headers={"Authorization": "Bearer dev-token"})

    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["error"]["code"] == "INVALID_REQUEST"


def test_authentication_failure_returns_401():
    orchestrator = ScriptedOrchestrator(response=AgentResponse.success("x", "unused"))
    client = TestClient(_build_app(orchestrator, auth_service=AlwaysDenyAuth()))

    resp = client.post("/agent/message", json=VALID_PAYLOAD, headers={"Authorization": "Bearer bad"})

    assert resp.status_code == 401
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["error"]["code"] == "AUTHENTICATION_FAILED"
    assert not orchestrator.received_requests


def test_rate_limit_exceeded_returns_429():
    orchestrator = ScriptedOrchestrator(response=AgentResponse.success("x", "unused"))
    client = TestClient(_build_app(orchestrator, rate_limiter=AlwaysDenyRateLimiter()))

    resp = client.post("/agent/message", json=VALID_PAYLOAD, headers={"Authorization": "Bearer dev-token"})

    assert resp.status_code == 429
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert not orchestrator.received_requests


def test_agent_failure_returns_500():
    orchestrator = ScriptedOrchestrator(raise_error=RuntimeError("boom"))
    client = TestClient(_build_app(orchestrator))

    resp = client.post("/agent/message", json=VALID_PAYLOAD, headers={"Authorization": "Bearer dev-token"})

    assert resp.status_code == 500
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["error"]["code"] == "AGENT_PROCESSING_ERROR"


def test_request_id_propagates_from_gateway_to_orchestrator_to_response():
    scripted = AgentResponse.success(request_id="will-be-overwritten", message="ok")
    orchestrator = ScriptedOrchestrator(response=scripted)
    client = TestClient(_build_app(orchestrator))

    payload = {**VALID_PAYLOAD, "requestId": "req-fixed-123"}
    resp = client.post("/agent/message", json=payload, headers={"Authorization": "Bearer dev-token"})

    assert resp.status_code == 200
    assert resp.json()["requestId"] == "req-fixed-123"
    assert orchestrator.received_requests[0].request_id == "req-fixed-123"


def test_request_id_generated_when_absent():
    scripted = AgentResponse.success(request_id="ignored", message="ok")
    orchestrator = ScriptedOrchestrator(response=scripted)
    client = TestClient(_build_app(orchestrator))

    resp = client.post("/agent/message", json=VALID_PAYLOAD, headers={"Authorization": "Bearer dev-token"})

    generated_id = resp.json()["requestId"]
    assert generated_id
    assert orchestrator.received_requests[0].request_id == generated_id


def test_health_check_returns_200():
    orchestrator = ScriptedOrchestrator(response=AgentResponse.success("x", "unused"))
    client = TestClient(_build_app(orchestrator))

    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "UP"


def test_ready_check_returns_200():
    orchestrator = ScriptedOrchestrator(response=AgentResponse.success("x", "unused"))
    client = TestClient(_build_app(orchestrator))

    resp = client.get("/ready")

    assert resp.status_code == 200

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent.agent_state import AgentState, AgentStatus
from app.agent.merchant_agent_orchestrator import MerchantAgentOrchestrator
from app.agent.orchestrator import AgentOrchestrator
from app.contracts.agent_request import AgentRequest
from app.contracts.agent_response import AgentResponse, AgentResponseStatus
from app.gateway import routes as gateway_routes
from app.gateway.authentication import AuthenticationService
from app.gateway.controller import AgentGatewayController
from app.gateway.error_handlers import register_gateway_error_handlers
from app.gateway.middleware import RequestLoggingMiddleware
from app.gateway.rate_limiter import RateLimiter


class PassthroughOrchestrator(AgentOrchestrator):
    """Wraps a fixed AgentResponse, standing in for a fully-run Agent Core
    (LLM + Tool Layer + Policy Engine) whose decision must reach the client
    byte-for-byte (aside from HTTP-level metadata)."""

    def __init__(self, response: AgentResponse):
        self._response = response

    def process(self, request: AgentRequest) -> AgentResponse:
        return self._response.model_copy(update={"request_id": request.request_id})


class AllowAllAuth(AuthenticationService):
    def authenticate(self, authorization, user_id) -> str:
        return user_id or "anonymous"


class AllowAllRateLimiter(RateLimiter):
    def allow(self, user_id: str) -> bool:
        return True


def test_controller_does_not_alter_semantic_response():
    """External Request -> AgentRequest -> AgentOrchestrator -> AgentResponse:
    the Controller must hand back the orchestrator's status/message/data
    unchanged."""
    agent_core_decision = AgentResponse(
        requestId="placeholder",
        status=AgentResponseStatus.WAITING_FOR_CONFIRMATION,
        message="I found 2 iPhones. Would you like to proceed?",
        data={"itemCount": 2, "product": "iPhone"},
    )
    controller = AgentGatewayController(PassthroughOrchestrator(agent_core_decision))

    request = AgentRequest.new(session_id="session-001", user_id="user-001", message="I want to buy 2 iPhones")
    response = controller.handle_request(request)

    assert response.status == AgentResponseStatus.WAITING_FOR_CONFIRMATION
    assert response.message == "I found 2 iPhones. Would you like to proceed?"
    assert response.data == {"itemCount": 2, "product": "iPhone"}
    assert response.request_id == request.request_id


def test_full_http_stack_preserves_agent_core_semantics():
    """AgentResponse -> External Response: the HTTP layer must only add
    status-code-level metadata, never change status/message/data."""
    agent_core_decision = AgentResponse(
        requestId="placeholder",
        status=AgentResponseStatus.WAITING_FOR_CONFIRMATION,
        message="I found 2 iPhones. Would you like to proceed?",
        data={"itemCount": 2},
    )

    app = FastAPI()
    app.include_router(gateway_routes.router)
    app.dependency_overrides[gateway_routes.get_agent_orchestrator] = lambda: PassthroughOrchestrator(
        agent_core_decision
    )
    app.dependency_overrides[gateway_routes.get_authentication_service] = lambda: AllowAllAuth()
    app.dependency_overrides[gateway_routes.get_rate_limiter] = lambda: AllowAllRateLimiter()
    app.add_middleware(RequestLoggingMiddleware)
    register_gateway_error_handlers(app)
    client = TestClient(app)

    resp = client.post(
        "/agent/message",
        json={
            "sessionId": "session-001",
            "userId": "user-001",
            "message": "I want to buy 2 iPhones",
            "channel": "web",
        },
        headers={"Authorization": "Bearer dev-token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "WAITING_FOR_CONFIRMATION"
    assert body["message"] == "I found 2 iPhones. Would you like to proceed?"
    assert body["data"] == {"itemCount": 2}


def test_request_id_is_identical_across_gateway_agent_request_and_response():
    agent_core_decision = AgentResponse(requestId="placeholder", status=AgentResponseStatus.SUCCESS, message="done")
    controller = AgentGatewayController(PassthroughOrchestrator(agent_core_decision))

    request = AgentRequest.new(session_id="s1", user_id="u1", message="hi", request_id="req-fixed-abc")
    response = controller.handle_request(request)

    assert request.request_id == "req-fixed-abc"
    assert response.request_id == "req-fixed-abc"


# ---------------------------------------------------------------------------
# MerchantAgentOrchestrator adapter: verifies the existing Agent Core's
# AgentState is translated faithfully into the Gateway's AgentResponse
# contract, without adding/removing meaning.
# ---------------------------------------------------------------------------
class FakeMerchantAgent:
    """Duck-types MerchantAgent.run() without needing a real LLM/tool
    client wiring."""

    def __init__(self, state: AgentState):
        self._state = state
        self.received = None

    def run(self, user_request, session_id=None, user_id=None, request_id=None):
        self.received = (user_request, session_id, user_id, request_id)
        return self._state


def test_orchestrator_maps_completed_state_to_success():
    state = AgentState.create(user_request="buy 2 iphones", session_id="s1", user_id=1)
    state.complete("Order placed for 2 iPhones.")

    orchestrator = MerchantAgentOrchestrator(FakeMerchantAgent(state))
    request = AgentRequest.new(session_id="s1", user_id="1", message="buy 2 iphones", request_id="req-1")
    response = orchestrator.process(request)

    assert response.status == AgentResponseStatus.SUCCESS
    assert response.message == "Order placed for 2 iPhones."
    assert response.request_id == "req-1"
    assert response.error is None


def test_orchestrator_maps_waiting_for_user_to_waiting_for_input():
    state = AgentState.create(user_request="buy iphones", session_id="s1", user_id=1)
    state.wait_for_user("How many iPhones would you like?")

    orchestrator = MerchantAgentOrchestrator(FakeMerchantAgent(state))
    request = AgentRequest.new(session_id="s1", user_id="1", message="buy iphones", request_id="req-2")
    response = orchestrator.process(request)

    assert response.status == AgentResponseStatus.WAITING_FOR_INPUT
    assert response.message == "How many iPhones would you like?"


def test_orchestrator_maps_failed_state_to_failed_with_structured_error():
    state = AgentState.create(user_request="buy iphones", session_id="s1", user_id=1)
    state.fail("The commerce tool service is currently unavailable.")

    orchestrator = MerchantAgentOrchestrator(FakeMerchantAgent(state))
    request = AgentRequest.new(session_id="s1", user_id="1", message="buy iphones", request_id="req-3")
    response = orchestrator.process(request)

    assert response.status == AgentResponseStatus.FAILED
    assert response.error is not None
    assert response.error.code == "AGENT_PROCESSING_ERROR"
    assert "unavailable" in response.error.message


def test_orchestrator_propagates_user_and_session_ids_to_agent_core():
    state = AgentState.create(user_request="hi", session_id="s1", user_id=1)
    state.complete("ok")
    fake_agent = FakeMerchantAgent(state)

    orchestrator = MerchantAgentOrchestrator(fake_agent)
    request = AgentRequest.new(session_id="session-xyz", user_id="42", message="hi")
    orchestrator.process(request)

    assert fake_agent.received == ("hi", "session-xyz", 42, request.request_id)

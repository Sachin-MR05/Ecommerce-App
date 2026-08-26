from __future__ import annotations

from typing import Optional

from fastapi import FastAPI

from app.agent.orchestrator import AgentOrchestrator
from app.gateway import routes as gateway_routes
from app.gateway.authentication import AuthenticationService, DevAuthenticationService
from app.gateway.error_handlers import register_gateway_error_handlers
from app.gateway.middleware import RequestLoggingMiddleware
from app.gateway.rate_limiter import InMemoryRateLimiter, RateLimiter


def include_gateway(
    app: FastAPI,
    orchestrator: AgentOrchestrator,
    auth_service: Optional[AuthenticationService] = None,
    rate_limiter: Optional[RateLimiter] = None,
) -> None:
    """One-call integration point for an existing FastAPI app.

    Mounts POST /agent/message, GET /health, GET /ready, wires dependency
    injection for the orchestrator/auth/rate-limiter, adds the structured
    request-logging middleware, and registers the Gateway's structured
    error handlers (400/401/429/500).

    Example (in the project's existing main.py)::

        from app.agent.merchant_agent_orchestrator import MerchantAgentOrchestrator
        from app.gateway.wiring import include_gateway

        orchestrator = MerchantAgentOrchestrator(merchant_agent)
        include_gateway(application, orchestrator)
    """

    resolved_auth_service = auth_service or DevAuthenticationService()
    resolved_rate_limiter = rate_limiter or InMemoryRateLimiter()

    app.include_router(gateway_routes.router)
    app.dependency_overrides[gateway_routes.get_agent_orchestrator] = lambda: orchestrator
    app.dependency_overrides[gateway_routes.get_authentication_service] = lambda: resolved_auth_service
    app.dependency_overrides[gateway_routes.get_rate_limiter] = lambda: resolved_rate_limiter

    app.add_middleware(RequestLoggingMiddleware)
    register_gateway_error_handlers(app)

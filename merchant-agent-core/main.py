from __future__ import annotations

import logging

from fastapi import FastAPI

from api import routes
from app.agent.merchant_agent import MerchantAgent
from app.agent.merchant_agent_orchestrator import MerchantAgentOrchestrator
from audit.audit_service import AuditService
from app.config.settings import get_settings
from failure_handling.failure_handler import FailureHandler
from app.gateway.wiring import include_gateway
from app.llm.llm_client import create_llm_client
from app.llm.prompt_manager import PromptManager
from app.tools.tool_client import ToolClient
from payment.payment_service import RazorpayToolPaymentService
from tools.order.order_tool_adapter import OrderToolAdapter
from tools.payment.razorpay_payment_tool_adapter import RazorpayPaymentToolAdapter
from transaction.transaction_orchestrator import TransactionOrchestrator


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Starting merchant-agent-core (tool service: %s)", settings.tool_service_url)

    tool_client = ToolClient(settings)
    llm_client = create_llm_client(settings)
    prompt_manager = PromptManager()

    # Deterministic Failure Handling + append-only Audit Service, shared by
    # both the agent's tool-calling path (Executor, via MerchantAgent) and
    # the Transaction/Payment Orchestrator. Both are process-local here
    # (in-memory idempotency store, in-memory audit repository) - see
    # app/audit/audit_repository.py for swapping in a durable JSONL-backed
    # (or future database-backed) repository.
    failure_handler = FailureHandler()
    audit_service = AuditService()

    def get_merchant_agent() -> MerchantAgent:
        return MerchantAgent(
            llm_client=llm_client,
            tool_client=tool_client,
            prompt_manager=prompt_manager,
            max_iterations=settings.agent_max_iterations,
            failure_handler=failure_handler,
            audit_service=audit_service,
        )

    merchant_agent = get_merchant_agent()
    orchestrator = MerchantAgentOrchestrator(merchant_agent)

    # Transaction / Payment Orchestrator - constructed and wired with the
    # same Failure Handling + Audit Service instances so its audit trail
    # and retry/recovery decisions share one process-local view. Not yet
    # reachable via a Gateway route (no checkout endpoint exists yet); kept
    # on app.state so a future route/Policy Engine integration can use it
    # without re-wiring these dependencies.
    payment_tool_adapter = RazorpayPaymentToolAdapter(tool_client)
    order_tool_adapter = OrderToolAdapter(tool_client)
    payment_service = RazorpayToolPaymentService(payment_tool_adapter, order_tool_adapter)
    transaction_orchestrator = TransactionOrchestrator(
        payment_service=payment_service,
        failure_handler=failure_handler,
        audit_service=audit_service,
    )

    application = FastAPI(title="Merchant Agent Core")
    application.include_router(routes.router)
    application.dependency_overrides[routes.get_merchant_agent] = get_merchant_agent
    application.state.transaction_orchestrator = transaction_orchestrator
    application.state.audit_service = audit_service
    application.state.failure_handler = failure_handler

    include_gateway(application, orchestrator)  # adds /agent/message, /health, /ready

    @application.on_event("shutdown")
    def shutdown() -> None:
        tool_client.close()

    return application


app = create_app()

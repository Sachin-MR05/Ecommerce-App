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
from monitoring.llm_instrumentation import TimingLLMClient
from monitoring.store import MonitoringStore
from monitoring.wiring import include_monitoring
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

    # Created here (rather than inside monitoring/wiring.py) so it can be
    # threaded into the LLM timing wrapper below before the monitoring
    # module is mounted - include_monitoring() reuses this same instance
    # instead of creating its own.
    monitoring_store = MonitoringStore()

    # Wraps whatever provider create_llm_client() picked (OpenAI/Gemini/
    # HuggingFace/Echo/Fallback) with latency timing only - no behavior,
    # retry, or fallback logic changes. See monitoring/llm_instrumentation.py.
    llm_client = TimingLLMClient(create_llm_client(settings), on_latency=monitoring_store.record_llm_latency)
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

    # Monitoring module (dashboard backend) - REST + WebSocket, read-only
    # observer of audit_service/transaction_orchestrator/the LLM client.
    # See monitoring/wiring.py. Mounted last so it never affects error
    # handler or middleware ordering for the existing Gateway routes above.
    include_monitoring(
        application,
        audit_service=audit_service,
        transaction_orchestrator=transaction_orchestrator,
        tool_service_url=settings.tool_service_url,
        dashboard_cors_origins=settings.dashboard_cors_origins,
        store=monitoring_store,
    )

    @application.on_event("shutdown")
    def shutdown() -> None:
        tool_client.close()

    return application


app = create_app()

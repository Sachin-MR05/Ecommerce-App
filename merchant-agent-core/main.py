from __future__ import annotations

import logging

from fastapi import FastAPI

from api import routes
from app.agent.merchant_agent import MerchantAgent
from app.config.settings import get_settings
from app.llm.llm_client import create_llm_client
from app.llm.prompt_manager import PromptManager
from app.tools.tool_client import ToolClient
from app.agent.merchant_agent_orchestrator import MerchantAgentOrchestrator
from app.gateway.wiring import include_gateway

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

    def get_merchant_agent() -> MerchantAgent:
        return MerchantAgent(
            llm_client=llm_client,
            tool_client=tool_client,
            prompt_manager=prompt_manager,
            max_iterations=settings.agent_max_iterations,
        )

    merchant_agent = MerchantAgent(
       llm_client=llm_client,
       tool_client=tool_client,
       prompt_manager=prompt_manager,
       max_iterations=settings.agent_max_iterations,
   )
    orchestrator = MerchantAgentOrchestrator(merchant_agent)
    include_gateway(application, orchestrator)  # adds /agent/message, /health, /ready

    application = FastAPI(title="Merchant Agent Core")
    application.include_router(routes.router)
    application.dependency_overrides[routes.get_merchant_agent] = get_merchant_agent

    

    @application.on_event("shutdown")
    def shutdown() -> None:
        tool_client.close()

    return application


app = create_app()

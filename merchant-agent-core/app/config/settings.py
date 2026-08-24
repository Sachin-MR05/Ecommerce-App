from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"


class Settings(BaseSettings):
    """Centralized configuration, populated from environment variables (and
    a local .env file during development - see .env.example). Nothing here
    has a hardcoded API key, LLM URL, or Java service URL as a real default;
    TOOL_SERVICE_URL in particular is required so the Python service can
    never silently point at a hardcoded "localhost".
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    llm_provider: LLMProvider = Field(default=LLMProvider.HUGGINGFACE, alias="LLM_PROVIDER")
    # Free HuggingFace model - no API token required (anonymous, rate-limited).
    # Switch to any OpenAI-compatible HF model by changing LLM_MODEL.
    llm_model: str = Field(default="HuggingFaceH4/zephyr-7b-beta", alias="LLM_MODEL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    # Override the LLM provider base URL (e.g. for HuggingFace Inference API).
    llm_base_url: str = Field(
        default="https://api-inference.huggingface.co",
        alias="LLM_BASE_URL",
    )

    tool_service_url: str = Field(..., alias="TOOL_SERVICE_URL")

    agent_max_iterations: int = Field(default=10, alias="AGENT_MAX_ITERATIONS")
    tool_timeout_seconds: int = Field(default=30, alias="TOOL_TIMEOUT_SECONDS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache
def get_settings() -> Settings:
    """Cached Settings instance - construct once per process."""
    return Settings()


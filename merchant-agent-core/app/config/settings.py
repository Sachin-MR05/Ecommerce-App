from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
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
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
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
    gemini_api_key: str = Field(
        default="",
        alias="GEMINI_API_KEY",
        validation_alias=AliasChoices("GEMINI_API_KEY", "Gemini_API_Key"),
    )
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
        alias="GEMINI_BASE_URL",
        validation_alias=AliasChoices("GEMINI_BASE_URL", "GEMNI_BASE_URL"),
    )
    gemini_fallback_base_url: str = Field(
        default="",
        alias="GEMINI_FALLBACK_BASE_URL",
        validation_alias=AliasChoices("GEMINI_FALLBACK_BASE_URL", "GEMNI_FALLBACK_BASE_URL"),
    )
    llm_max_output_tokens: int = Field(default=64, alias="LLM_MAX_OUTPUT_TOKENS")

    tool_service_url: str = Field(..., alias="TOOL_SERVICE_URL")

    agent_max_iterations: int = Field(default=10, alias="AGENT_MAX_ITERATIONS")
    tool_timeout_seconds: int = Field(default=30, alias="TOOL_TIMEOUT_SECONDS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Comma-separated list of origins allowed to call this API and open the
    # /monitoring/ws WebSocket from a browser - the monitoring-dashboard
    # Vite dev server (http://localhost:5173) by default. Only used by
    # monitoring/wiring.py's CORS setup; unrelated to Java Tool Layer auth.
    dashboard_cors_origins: str = Field(default="http://localhost:5173", alias="DASHBOARD_CORS_ORIGINS")


@lru_cache
def get_settings() -> Settings:
    """Cached Settings instance - construct once per process."""
    return Settings()


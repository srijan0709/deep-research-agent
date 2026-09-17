"""Centralized, environment-driven configuration.

All external configuration must come from environment variables (see
`.env.example`). No credentials or magic numbers should be hardcoded
elsewhere in the application.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "") or "")

    # Search
    search_provider: str = field(default_factory=lambda: os.getenv("SEARCH_PROVIDER", "duckduckgo"))
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))

    # Database
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./research.db"))

    # Limits
    max_research_tasks: int = field(default_factory=lambda: _int("MAX_RESEARCH_TASKS", 8))
    max_sources_per_task: int = field(default_factory=lambda: _int("MAX_SOURCES_PER_TASK", 10))
    max_research_time_seconds: int = field(default_factory=lambda: _int("MAX_RESEARCH_TIME_SECONDS", 600))

    # Timeouts
    llm_timeout_seconds: int = field(default_factory=lambda: _int("LLM_TIMEOUT_SECONDS", 60))
    search_timeout_seconds: int = field(default_factory=lambda: _int("SEARCH_TIMEOUT_SECONDS", 10))
    task_timeout_seconds: int = field(default_factory=lambda: _int("TASK_TIMEOUT_SECONDS", 120))

    # Retries
    max_retries: int = field(default_factory=lambda: _int("MAX_RETRIES", 3))

    # Depth presets: (num_tasks, sources_per_task)
    depth_presets: dict = field(default_factory=lambda: {
        "Quick": (3, 5),
        "Standard": (5, 8),
        "Deep": (8, 10),
    })

    prompt_version: str = "v1"


settings = Settings()

# Rough per-1K-token pricing used only for cost estimation display. These are
# intentionally simple; a production system would source live pricing.
MODEL_PRICING_PER_1K = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
}


def get_model_pricing(model: str) -> dict:
    return MODEL_PRICING_PER_1K.get(model, {"input": 0.0005, "output": 0.0015})

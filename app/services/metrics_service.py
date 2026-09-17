"""Cost/token accounting and structured event logging (spec sections 43-44)."""
from __future__ import annotations

import structlog

from app.models.metrics import ResearchMetrics
from app.storage import repositories as repo
from app.tools.llm_client import estimate_cost

logger = structlog.get_logger("deep_research_agent")


class MetricsAccumulator:
    def __init__(self, research_id: str):
        self.metrics = ResearchMetrics(research_id=research_id)

    def record_llm_call(self, model: str, input_tokens: int, output_tokens: int, latency_ms: float) -> None:
        self.metrics.llm_calls += 1
        self.metrics.input_tokens += input_tokens
        self.metrics.output_tokens += output_tokens
        self.metrics.estimated_cost += estimate_cost(model, input_tokens, output_tokens)

    def record_search_call(self) -> None:
        self.metrics.search_calls += 1

    def finalize(self, duration_seconds: float) -> ResearchMetrics:
        self.metrics.duration_seconds = duration_seconds
        repo.save_metrics(self.metrics.research_id, self.metrics.model_dump())
        return self.metrics


def log_event(research_id: str, event: str, **fields) -> None:
    payload = {"event": event, "research_id": research_id, **fields}
    logger.info(event, research_id=research_id, **fields)
    repo.save_event(research_id, payload)

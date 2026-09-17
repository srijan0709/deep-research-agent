"""Metrics / observability event models (see spec sections 43-44)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    event: str
    research_id: str
    task_id: Optional[str] = None
    tool: Optional[str] = None
    latency_ms: Optional[float] = None
    success: Optional[bool] = None
    detail: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LLMCallMetric(BaseModel):
    research_id: str
    stage: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost: float = 0.0


class ResearchMetrics(BaseModel):
    research_id: str
    duration_seconds: float = 0.0
    llm_calls: int = 0
    search_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    sources_discovered: int = 0
    sources_selected: int = 0
    evidence_blocks: int = 0
    claims_generated: int = 0
    claims_verified: int = 0
    claims_unsupported: int = 0

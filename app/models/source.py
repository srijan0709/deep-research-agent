"""Source & evidence Pydantic models (see spec sections 9-10)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import SourceType


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Source(BaseModel):
    source_id: str
    research_id: str
    url: str
    title: str = ""
    publisher: str = ""
    published_at: Optional[str] = None
    retrieved_at: str = Field(default_factory=_now)
    source_type: SourceType = SourceType.OTHER
    content_hash: str = ""
    relevance_score: float = 0.0


class Evidence(BaseModel):
    evidence_id: str
    source_id: str
    research_id: str
    task_id: Optional[str] = None
    text: str
    url: str = ""
    title: str = ""
    publisher: str = ""
    published_at: Optional[str] = None
    retrieved_at: str = Field(default_factory=_now)
    relevance_score: float = 0.0

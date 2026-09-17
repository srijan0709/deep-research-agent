"""Research job / task / plan models (see spec sections 7, 16-17)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import Priority, ResearchStatus, TaskStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlanTask(BaseModel):
    """A single task inside the LLM-generated research plan (pre-validation)."""

    id: str
    question: str
    priority: Priority = Priority.MEDIUM
    search_queries: List[str] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    title: str
    objective: str
    tasks: List[PlanTask]


class ResearchTask(BaseModel):
    task_id: str
    research_id: str
    question: str
    priority: Priority = Priority.MEDIUM
    search_queries: List[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    attempt: int = 0
    max_attempts: int = 3
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class ResearchJob(BaseModel):
    research_id: str
    question: str
    depth: str = "Standard"
    status: ResearchStatus = ResearchStatus.CREATED
    title: str = ""
    objective: str = ""
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    completed_at: Optional[str] = None
    error: Optional[str] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    report: Optional[str] = None
    model: str = ""
    prompt_version: str = "v1"

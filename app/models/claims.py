"""Claim models (see spec sections 11-13)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import VerificationStatus


class Claim(BaseModel):
    claim_id: str
    research_id: str
    task_id: Optional[str] = None
    text: str
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    verification_status: VerificationStatus = VerificationStatus.PENDING
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    reason: str = ""


class CandidateClaim(BaseModel):
    """Claim produced by the researcher stage, before verification."""

    claim: str
    evidence: str
    source_id: str
    confidence: float = 0.5


class VerificationResult(BaseModel):
    claim_id: str
    status: VerificationStatus
    confidence: float
    reason: str = ""
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)

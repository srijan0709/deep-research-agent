"""Verification Agent (spec section 12)."""
from __future__ import annotations

from typing import List

from app.agents.prompt_loader import load_prompt
from app.models.claims import VerificationResult
from app.models.source import Evidence
from app.tools.llm_client import LLMCallResult, call_structured


def verify_claim(
    claim_id: str,
    claim_text: str,
    evidence_items: List[Evidence],
    model: str | None = None,
) -> tuple[VerificationResult, LLMCallResult]:
    system_prompt = load_prompt("verifier_v1.txt")
    evidence_block = "\n".join(
        f"[evidence_id={e.evidence_id}] ({e.title or e.publisher})\n{e.text}" for e in evidence_items
    ) or "(no evidence supplied)"
    user_prompt = (
        f"Claim (claim_id={claim_id}):\n{claim_text}\n\nEvidence:\n{evidence_block}"
    )
    result, call_result = call_structured(system_prompt, user_prompt, VerificationResult, model=model)
    result.claim_id = claim_id
    return result, call_result

"""Synthesis Agent (spec section 14)."""
from __future__ import annotations

from typing import List

from app.agents.prompt_loader import load_prompt
from app.models.claims import Claim
from app.models.research import ResearchPlan
from app.models.source import Source
from app.tools.llm_client import LLMCallResult, call_text


def build_source_citation_map(sources: List[Source]) -> dict[str, int]:
    """Assigns stable numeric citation markers to sources, in relevance order."""
    ordered = sorted(sources, key=lambda s: s.relevance_score, reverse=True)
    return {s.source_id: i + 1 for i, s in enumerate(ordered)}


def synthesize_report(
    question: str,
    plan: ResearchPlan,
    claims: List[Claim],
    sources: List[Source],
    citation_map: dict[str, int],
    model: str | None = None,
) -> tuple[str, LLMCallResult]:
    system_prompt = load_prompt("synthesizer_v1.txt")

    source_lines = []
    by_id = {s.source_id: s for s in sources}
    for source_id, n in sorted(citation_map.items(), key=lambda kv: kv[1]):
        s = by_id[source_id]
        source_lines.append(f"[{n}] {s.title or s.url} — {s.publisher or 'unknown publisher'} ({s.url})")

    claim_lines = []
    for c in claims:
        claim_lines.append(
            f"- ({c.verification_status.value}, confidence={c.confidence:.2f}) {c.text}"
        )

    user_prompt = (
        f"Research question:\n{question}\n\n"
        f"Research plan title: {plan.title}\nObjective: {plan.objective}\n\n"
        f"Verified claims:\n" + ("\n".join(claim_lines) or "(none)") + "\n\n"
        f"Available numbered sources (use ONLY these citation numbers):\n" + ("\n".join(source_lines) or "(none)")
    )
    result = call_text(system_prompt, user_prompt, model=model)
    return result.content, result

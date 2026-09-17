"""Research Worker (spec section 8).

Executes a single task: query -> search -> normalize -> dedup -> rank ->
select -> extract evidence -> candidate claims.
"""
from __future__ import annotations

import uuid
from typing import List

from pydantic import BaseModel, Field

from app.agents.prompt_loader import load_prompt
from app.config import settings
from app.models.claims import CandidateClaim
from app.models.enums import SourceType
from app.models.research import ResearchTask
from app.models.source import Evidence, Source
from app.tools.llm_client import LLMCallResult, call_structured
from app.tools.search import SearchResult, content_hash_for, search_web

GOV_HINTS = (".gov", "worldbank", "imf.org", "rbi.org", "oecd", ".gov.in")
ACADEMIC_HINTS = ("arxiv", ".edu", "researchgate", "ssrn", "nber")
NEWS_HINTS = ("reuters", "bloomberg", "ft.com", "economist", "bbc", "cnbc", "wsj")


class ResearcherClaims(BaseModel):
    claims: List[CandidateClaim] = Field(default_factory=list)


def _classify_source(url: str) -> SourceType:
    lowered = url.lower()
    if any(h in lowered for h in GOV_HINTS):
        return SourceType.GOVERNMENT
    if any(h in lowered for h in ACADEMIC_HINTS):
        return SourceType.RESEARCH
    if any(h in lowered for h in NEWS_HINTS):
        return SourceType.NEWS
    return SourceType.OTHER


def _score_source(result: SearchResult, source_type: SourceType, is_duplicate: bool) -> float:
    """Deterministic heuristic ranking (spec section 22)."""
    score = 0.0
    score += {"government": 3, "research": 3, "news": 2, "company": 1, "other": 0}[source_type.value]
    if result.snippet:
        score += 1
    if is_duplicate:
        score -= 5
    return score


def run_research_task(
    task: ResearchTask,
    existing_hashes: set[str],
    max_sources: int,
    model: str | None = None,
) -> tuple[List[Source], List[Evidence], List[CandidateClaim], List[LLMCallResult]]:
    """Runs the deterministic search/rank/select pipeline, then asks the LLM
    to extract candidate claims from the selected excerpts.
    """
    all_results: List[tuple[SearchResult, float, str]] = []
    seen_hashes = set(existing_hashes)

    for query in (task.search_queries or [task.question])[:4]:
        try:
            results = search_web(query, max_results=max_sources)
        except Exception:
            continue
        for r in results:
            chash = content_hash_for(r.url, r.title)
            is_dup = chash in seen_hashes
            source_type = _classify_source(r.url)
            score = _score_source(r, source_type, is_dup)
            if not is_dup:
                seen_hashes.add(chash)
            all_results.append((r, score, chash))

    # Rank and select top N unique sources.
    all_results.sort(key=lambda x: x[1], reverse=True)
    selected: List[tuple[SearchResult, float, str]] = []
    used_hashes = set()
    for r, score, chash in all_results:
        if chash in used_hashes or score < 0:
            continue
        used_hashes.add(chash)
        selected.append((r, score, chash))
        if len(selected) >= max_sources:
            break

    sources: List[Source] = []
    evidence: List[Evidence] = []
    excerpt_lines = []
    for r, score, chash in selected:
        source_id = f"src_{uuid.uuid4().hex[:10]}"
        source_type = _classify_source(r.url)
        source = Source(
            source_id=source_id, research_id=task.research_id, url=r.url, title=r.title,
            publisher=r.publisher, source_type=source_type, content_hash=chash,
            relevance_score=round(min(max(score, 0) / 6.0, 1.0), 2),
        )
        sources.append(source)
        ev = Evidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:10]}", source_id=source_id, research_id=task.research_id,
            task_id=task.task_id, text=r.snippet, url=r.url, title=r.title, publisher=r.publisher,
            relevance_score=source.relevance_score,
        )
        evidence.append(ev)
        excerpt_lines.append(f"[source_id={source_id}] {r.title}\n{r.snippet}\n")

    call_results: List[LLMCallResult] = []
    candidate_claims: List[CandidateClaim] = []
    if excerpt_lines:
        system_prompt = load_prompt("researcher_v1.txt")
        user_prompt = f"Task question:\n{task.question}\n\nSearch result excerpts:\n\n" + "\n".join(excerpt_lines)
        try:
            parsed, call_result = call_structured(system_prompt, user_prompt, ResearcherClaims, model=model)
            candidate_claims = parsed.claims
            call_results.append(call_result)
        except Exception:
            candidate_claims = []

    return sources, evidence, candidate_claims, call_results

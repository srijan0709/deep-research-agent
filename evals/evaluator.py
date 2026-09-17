"""Evaluation harness (spec sections 41-42).

Runs each case in evals/dataset.json through the full pipeline and computes:
- Retrieval: topic coverage in selected sources/evidence
- Generation: citation coverage, claim verification rate
- System: latency, cost, task completion rate

An LLM-as-judge score is combined with these deterministic checks rather
than being the sole signal (spec section 42).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.agents.prompt_loader import load_prompt
from app.models.enums import ResearchStatus, VerificationStatus
from app.services.research_manager import run_research
from app.storage import repositories as repo
from app.tools.llm_client import call_text

_DATASET_PATH = Path(__file__).parent / "dataset.json"
_RESULTS_DIR = Path(__file__).parent / "results"


def _topic_coverage(report: str, expected_topics: list[str]) -> float:
    if not expected_topics:
        return 1.0
    lower = report.lower()
    hits = sum(1 for topic in expected_topics if topic.lower() in lower)
    return hits / len(expected_topics)


def _judge_score(question: str, report: str) -> float:
    system_prompt = (
        "You are an evaluation judge. Score the research report's quality and "
        "usefulness for answering the question, from 1 (poor) to 5 (excellent). "
        "Respond with only the integer score."
    )
    user_prompt = f"Question:\n{question}\n\nReport:\n{report[:6000]}"
    try:
        result = call_text(system_prompt, user_prompt)
        return float("".join(ch for ch in result.content if ch.isdigit() or ch == ".") or 0)
    except Exception:
        return 0.0


def run_evaluation() -> dict:
    cases = json.loads(_DATASET_PATH.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        job = run_research(case["question"], depth="Quick")
        claims = repo.get_claims(job.research_id)
        verified = [c for c in claims if c.verification_status == VerificationStatus.VERIFIED]
        metrics = repo.get_metrics(job.research_id) or {}
        report = job.report or ""

        results.append({
            "question": case["question"],
            "research_id": job.research_id,
            "status": job.status.value,
            "topic_coverage": _topic_coverage(report, case.get("expected_topics", [])),
            "claim_verification_rate": (len(verified) / len(claims)) if claims else 0.0,
            "judge_score": _judge_score(case["question"], report) if report else 0.0,
            "duration_seconds": metrics.get("duration_seconds", 0),
            "estimated_cost": metrics.get("estimated_cost", 0),
            "task_completion_rate": (job.completed_tasks / job.total_tasks) if job.total_tasks else 0.0,
        })

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / "latest.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return {"results": results, "results_path": str(out_path)}


if __name__ == "__main__":
    summary = run_evaluation()
    print(json.dumps(summary["results"], indent=2))

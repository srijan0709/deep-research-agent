"""Research Manager: the deterministic orchestrator (spec sections 16-20).

Owns the job state machine, per-task retry/timeout handling, evidence
persistence, claim verification, synthesis and citation validation. The LLM
is only invoked through the agent modules for reasoning steps.
"""
from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from app.agents.planner import generate_plan
from app.agents.researcher import run_research_task
from app.agents.synthesizer import build_source_citation_map, synthesize_report
from app.agents.verifier import verify_claim
from app.config import settings
from app.models.claims import Claim
from app.models.enums import ResearchStatus, TaskStatus, VerificationStatus
from app.models.research import ResearchJob, ResearchPlan, ResearchTask
from app.services.citation_service import validate_citations
from app.services.metrics_service import MetricsAccumulator, log_event
from app.storage import repositories as repo

ProgressCallback = Optional[Callable[[ResearchJob], None]]


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _new_job(question: str, depth: str) -> ResearchJob:
    research_id = f"research_{uuid.uuid4().hex[:8]}"
    job = ResearchJob(research_id=research_id, question=question, depth=depth, model=settings.llm_model)
    repo.save_job(job)
    return job


def _update_status(job: ResearchJob, status: ResearchStatus, on_progress: ProgressCallback = None) -> None:
    job.status = status
    job.updated_at = _now_iso()
    repo.save_job(job)
    log_event(job.research_id, "status_changed", detail=status.value)
    if on_progress:
        on_progress(job)


def run_research(question: str, depth: str = "Standard", on_progress: ProgressCallback = None) -> ResearchJob:
    """Runs the full pipeline synchronously and returns the completed job.

    Intended to be called from a worker thread by the Gradio UI so the UI
    event loop is not blocked.
    """
    job = _new_job(question, depth)
    start_time = time.perf_counter()
    metrics = MetricsAccumulator(job.research_id)
    num_tasks, max_sources = settings.depth_presets.get(depth, (5, 8))
    num_tasks = min(num_tasks, settings.max_research_tasks)
    max_sources = min(max_sources, settings.max_sources_per_task)

    try:
        # ---------------- PLANNING ----------------
        _update_status(job, ResearchStatus.PLANNING, on_progress)
        plan, call_result = generate_plan(question, num_tasks)
        metrics.record_llm_call(settings.llm_model, call_result.input_tokens, call_result.output_tokens, call_result.latency_ms)
        job.title = plan.title
        job.objective = plan.objective
        job.total_tasks = len(plan.tasks)
        repo.save_job(job)
        log_event(job.research_id, "planning_completed", detail=f"{len(plan.tasks)} tasks")

        tasks = []
        for pt in plan.tasks:
            task = ResearchTask(
                task_id=f"task_{uuid.uuid4().hex[:8]}", research_id=job.research_id,
                question=pt.question, priority=pt.priority, search_queries=pt.search_queries,
                max_attempts=settings.max_retries,
            )
            repo.save_task(task)
            tasks.append(task)

        # ---------------- RESEARCHING ----------------
        _update_status(job, ResearchStatus.RESEARCHING, on_progress)
        all_candidate_claims = []
        seen_hashes: set[str] = set()

        def _execute_task(task: ResearchTask):
            local_hashes = set(seen_hashes)
            task.status = TaskStatus.RUNNING
            task.started_at = _now_iso()
            repo.save_task(task)
            last_error = None
            for attempt in range(1, task.max_attempts + 1):
                task.attempt = attempt
                try:
                    sources, evidence, candidates, call_results = run_research_task(task, local_hashes, max_sources)
                    for s in sources:
                        repo.save_source(s)
                    for e in evidence:
                        repo.save_evidence(e)
                    for cr in call_results:
                        metrics.record_llm_call(settings.llm_model, cr.input_tokens, cr.output_tokens, cr.latency_ms)
                    metrics.record_search_call()
                    task.status = TaskStatus.COMPLETED
                    task.result = f"{len(sources)} sources, {len(candidates)} candidate claims"
                    task.completed_at = _now_iso()
                    repo.save_task(task)
                    log_event(job.research_id, "tool_call", task_id=task.task_id, tool="web_search", success=True)
                    return sources, evidence, candidates
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)
                    task.status = TaskStatus.RETRYING if attempt < task.max_attempts else TaskStatus.FAILED
                    repo.save_task(task)
                    log_event(job.research_id, "tool_call", task_id=task.task_id, tool="web_search", success=False, detail=last_error)
            task.error = last_error
            task.status = TaskStatus.FAILED
            task.completed_at = _now_iso()
            repo.save_task(task)
            return [], [], []

        with ThreadPoolExecutor(max_workers=min(5, max(1, len(tasks)))) as executor:
            futures = {executor.submit(_execute_task, t): t for t in tasks}
            for future in as_completed(futures):
                sources, evidence, candidates = future.result()
                for s in sources:
                    seen_hashes.add(s.content_hash)
                task = futures[future]
                for c in candidates:
                    all_candidate_claims.append((task.task_id, c))
                job.completed_tasks += 1
                repo.save_job(job)
                if on_progress:
                    on_progress(job)

        # ---------------- VERIFYING ----------------
        _update_status(job, ResearchStatus.VERIFYING, on_progress)
        claims: list[Claim] = []
        for task_id, candidate in all_candidate_claims:
            claim_id = f"claim_{uuid.uuid4().hex[:8]}"
            related_evidence = [e for e in repo.get_evidence(job.research_id) if e.source_id == candidate.source_id]
            try:
                v_result, cr = verify_claim(claim_id, candidate.claim, related_evidence)
                metrics.record_llm_call(settings.llm_model, cr.input_tokens, cr.output_tokens, cr.latency_ms)
                claim = Claim(
                    claim_id=claim_id, research_id=job.research_id, task_id=task_id, text=candidate.claim,
                    evidence_ids=[e.evidence_id for e in related_evidence], confidence=v_result.confidence,
                    verification_status=v_result.status, supporting_evidence_ids=v_result.supporting_evidence_ids,
                    contradicting_evidence_ids=v_result.contradicting_evidence_ids, reason=v_result.reason,
                )
            except Exception:  # noqa: BLE001
                claim = Claim(
                    claim_id=claim_id, research_id=job.research_id, task_id=task_id, text=candidate.claim,
                    evidence_ids=[e.evidence_id for e in related_evidence], confidence=candidate.confidence,
                    verification_status=VerificationStatus.UNSUPPORTED,
                )
            repo.save_claim(claim)
            claims.append(claim)
            log_event(job.research_id, "claim_verified", detail=claim.verification_status.value)

        verified_claims = [c for c in claims if c.verification_status in (
            VerificationStatus.VERIFIED, VerificationStatus.PARTIALLY_SUPPORTED, VerificationStatus.CONTRADICTED,
        )]

        # ---------------- SYNTHESIZING ----------------
        _update_status(job, ResearchStatus.SYNTHESIZING, on_progress)
        sources = repo.get_sources(job.research_id)
        citation_map = build_source_citation_map(sources)
        report, cr = synthesize_report(question, plan, verified_claims, sources, citation_map)
        metrics.record_llm_call(settings.llm_model, cr.input_tokens, cr.output_tokens, cr.latency_ms)

        # ---------------- VALIDATING ----------------
        _update_status(job, ResearchStatus.VALIDATING, on_progress)
        validation = validate_citations(report, citation_map, sources)
        if validation.invalid_markers:
            log_event(job.research_id, "citation_validation_failed", detail=str(validation.invalid_markers))

        job.report = validation.valid_report
        job.status = ResearchStatus.COMPLETED
        job.completed_at = _now_iso()
        job.updated_at = job.completed_at
        repo.save_job(job)

        duration = time.perf_counter() - start_time
        m = metrics.finalize(duration)
        m.sources_discovered = len(sources)
        m.sources_selected = len(sources)
        m.evidence_blocks = len(repo.get_evidence(job.research_id))
        m.claims_generated = len(claims)
        m.claims_verified = len(verified_claims)
        m.claims_unsupported = len([c for c in claims if c.verification_status == VerificationStatus.UNSUPPORTED])
        repo.save_metrics(job.research_id, m.model_dump())

        log_event(job.research_id, "research_completed")
        if on_progress:
            on_progress(job)
        return job

    except Exception as exc:  # noqa: BLE001
        job.status = ResearchStatus.FAILED
        job.error = str(exc)
        job.updated_at = _now_iso()
        repo.save_job(job)
        log_event(job.research_id, "research_failed", detail=str(exc))
        if on_progress:
            on_progress(job)
        return job

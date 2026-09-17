"""Repository layer: the only place SQL lives. Everything else uses these
functions and Pydantic models, keeping the persistence mechanism swappable.
"""
from __future__ import annotations

import json
from typing import List, Optional

from app.models.claims import Claim
from app.models.enums import (
    Priority,
    ResearchStatus,
    SourceType,
    TaskStatus,
    VerificationStatus,
)
from app.models.research import ResearchJob, ResearchTask
from app.models.source import Evidence, Source
from app.storage.database import transaction


# ---------------------------------------------------------------- research_jobs
def save_job(job: ResearchJob) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO research_jobs
                (id, question, depth, status, title, objective, created_at,
                 updated_at, completed_at, error, total_tasks, completed_tasks,
                 report, model, prompt_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                question=excluded.question, depth=excluded.depth,
                status=excluded.status, title=excluded.title,
                objective=excluded.objective, updated_at=excluded.updated_at,
                completed_at=excluded.completed_at, error=excluded.error,
                total_tasks=excluded.total_tasks,
                completed_tasks=excluded.completed_tasks,
                report=excluded.report, model=excluded.model,
                prompt_version=excluded.prompt_version
            """,
            (
                job.research_id, job.question, job.depth, job.status.value,
                job.title, job.objective, job.created_at, job.updated_at,
                job.completed_at, job.error, job.total_tasks,
                job.completed_tasks, job.report, job.model, job.prompt_version,
            ),
        )


def get_job(research_id: str) -> Optional[ResearchJob]:
    from app.storage.database import get_connection
    conn = get_connection()
    row = conn.execute("SELECT * FROM research_jobs WHERE id=?", (research_id,)).fetchone()
    if not row:
        return None
    return ResearchJob(
        research_id=row["id"], question=row["question"], depth=row["depth"] or "Standard",
        status=ResearchStatus(row["status"]), title=row["title"] or "", objective=row["objective"] or "",
        created_at=row["created_at"], updated_at=row["updated_at"], completed_at=row["completed_at"],
        error=row["error"], total_tasks=row["total_tasks"] or 0, completed_tasks=row["completed_tasks"] or 0,
        report=row["report"], model=row["model"] or "", prompt_version=row["prompt_version"] or "v1",
    )


# ---------------------------------------------------------------- research_tasks
def save_task(task: ResearchTask) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO research_tasks
                (id, research_id, question, priority, search_queries, status,
                 attempt, max_attempts, result, error, started_at, completed_at,
                 created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status, attempt=excluded.attempt,
                result=excluded.result, error=excluded.error,
                started_at=excluded.started_at, completed_at=excluded.completed_at,
                updated_at=excluded.updated_at
            """,
            (
                task.task_id, task.research_id, task.question, task.priority.value,
                json.dumps(task.search_queries), task.status.value, task.attempt,
                task.max_attempts, task.result, task.error, task.started_at,
                task.completed_at, task.created_at, task.updated_at,
            ),
        )


def get_tasks(research_id: str) -> List[ResearchTask]:
    from app.storage.database import get_connection
    conn = get_connection()
    rows = conn.execute("SELECT * FROM research_tasks WHERE research_id=? ORDER BY created_at", (research_id,)).fetchall()
    result = []
    for row in rows:
        result.append(ResearchTask(
            task_id=row["id"], research_id=row["research_id"], question=row["question"],
            priority=Priority(row["priority"] or "medium"),
            search_queries=json.loads(row["search_queries"] or "[]"),
            status=TaskStatus(row["status"]), attempt=row["attempt"] or 0,
            max_attempts=row["max_attempts"] or 3, result=row["result"], error=row["error"],
            started_at=row["started_at"], completed_at=row["completed_at"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        ))
    return result


# ---------------------------------------------------------------- sources
def save_source(source: Source) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO sources (id, research_id, url, title, publisher, published_at,
                retrieved_at, source_type, content_hash, relevance_score)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET relevance_score=excluded.relevance_score
            """,
            (source.source_id, source.research_id, source.url, source.title, source.publisher,
             source.published_at, source.retrieved_at, source.source_type.value,
             source.content_hash, source.relevance_score),
        )


def get_sources(research_id: str) -> List[Source]:
    from app.storage.database import get_connection
    conn = get_connection()
    rows = conn.execute("SELECT * FROM sources WHERE research_id=? ORDER BY relevance_score DESC", (research_id,)).fetchall()
    return [
        Source(
            source_id=row["id"], research_id=row["research_id"], url=row["url"], title=row["title"] or "",
            publisher=row["publisher"] or "", published_at=row["published_at"], retrieved_at=row["retrieved_at"],
            source_type=SourceType(row["source_type"] or "other"), content_hash=row["content_hash"] or "",
            relevance_score=row["relevance_score"] or 0.0,
        ) for row in rows
    ]


def find_source_by_hash(research_id: str, content_hash: str) -> Optional[Source]:
    from app.storage.database import get_connection
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM sources WHERE research_id=? AND content_hash=? LIMIT 1",
        (research_id, content_hash),
    ).fetchone()
    if not row:
        return None
    return Source(
        source_id=row["id"], research_id=row["research_id"], url=row["url"], title=row["title"] or "",
        publisher=row["publisher"] or "", published_at=row["published_at"], retrieved_at=row["retrieved_at"],
        source_type=SourceType(row["source_type"] or "other"), content_hash=row["content_hash"] or "",
        relevance_score=row["relevance_score"] or 0.0,
    )


# ---------------------------------------------------------------- evidence
def save_evidence(evidence: Evidence) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO evidence (id, source_id, research_id, task_id, text, url, title,
                publisher, published_at, retrieved_at, relevance_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO NOTHING
            """,
            (evidence.evidence_id, evidence.source_id, evidence.research_id, evidence.task_id,
             evidence.text, evidence.url, evidence.title, evidence.publisher, evidence.published_at,
             evidence.retrieved_at, evidence.relevance_score),
        )


def get_evidence(research_id: str) -> List[Evidence]:
    from app.storage.database import get_connection
    conn = get_connection()
    rows = conn.execute("SELECT * FROM evidence WHERE research_id=?", (research_id,)).fetchall()
    return [
        Evidence(
            evidence_id=row["id"], source_id=row["source_id"], research_id=row["research_id"],
            task_id=row["task_id"], text=row["text"], url=row["url"] or "", title=row["title"] or "",
            publisher=row["publisher"] or "", published_at=row["published_at"], retrieved_at=row["retrieved_at"],
            relevance_score=row["relevance_score"] or 0.0,
        ) for row in rows
    ]


def get_evidence_by_ids(evidence_ids: List[str]) -> List[Evidence]:
    if not evidence_ids:
        return []
    from app.storage.database import get_connection
    conn = get_connection()
    placeholders = ",".join("?" * len(evidence_ids))
    rows = conn.execute(f"SELECT * FROM evidence WHERE id IN ({placeholders})", evidence_ids).fetchall()
    return [
        Evidence(
            evidence_id=row["id"], source_id=row["source_id"], research_id=row["research_id"],
            task_id=row["task_id"], text=row["text"], url=row["url"] or "", title=row["title"] or "",
            publisher=row["publisher"] or "", published_at=row["published_at"], retrieved_at=row["retrieved_at"],
            relevance_score=row["relevance_score"] or 0.0,
        ) for row in rows
    ]


# ---------------------------------------------------------------- claims
def save_claim(claim: Claim) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO claims (id, research_id, task_id, text, confidence, verification_status, reason, created_at)
            VALUES (?,?,?,?,?,?,?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                confidence=excluded.confidence, verification_status=excluded.verification_status,
                reason=excluded.reason
            """,
            (claim.claim_id, claim.research_id, claim.task_id, claim.text, claim.confidence,
             claim.verification_status.value, claim.reason),
        )
        conn.execute("DELETE FROM claim_evidence WHERE claim_id=?", (claim.claim_id,))
        for eid in claim.supporting_evidence_ids:
            conn.execute("INSERT INTO claim_evidence (claim_id, evidence_id, relationship) VALUES (?,?,'supports')",
                         (claim.claim_id, eid))
        for eid in claim.contradicting_evidence_ids:
            conn.execute("INSERT INTO claim_evidence (claim_id, evidence_id, relationship) VALUES (?,?,'contradicts')",
                         (claim.claim_id, eid))


def get_claims(research_id: str) -> List[Claim]:
    from app.storage.database import get_connection
    conn = get_connection()
    rows = conn.execute("SELECT * FROM claims WHERE research_id=?", (research_id,)).fetchall()
    claims = []
    for row in rows:
        ce_rows = conn.execute("SELECT * FROM claim_evidence WHERE claim_id=?", (row["id"],)).fetchall()
        supporting = [r["evidence_id"] for r in ce_rows if r["relationship"] == "supports"]
        contradicting = [r["evidence_id"] for r in ce_rows if r["relationship"] == "contradicts"]
        claims.append(Claim(
            claim_id=row["id"], research_id=row["research_id"], task_id=row["task_id"], text=row["text"],
            evidence_ids=supporting + contradicting, confidence=row["confidence"] or 0.0,
            verification_status=VerificationStatus(row["verification_status"] or "pending"),
            supporting_evidence_ids=supporting, contradicting_evidence_ids=contradicting,
            reason=row["reason"] or "",
        ))
    return claims


# ---------------------------------------------------------------- metrics & events
def save_metrics(research_id: str, data: dict) -> None:
    with transaction() as conn:
        conn.execute(
            "INSERT INTO metrics (research_id, data) VALUES (?,?) ON CONFLICT(research_id) DO UPDATE SET data=excluded.data",
            (research_id, json.dumps(data)),
        )


def get_metrics(research_id: str) -> Optional[dict]:
    from app.storage.database import get_connection
    conn = get_connection()
    row = conn.execute("SELECT data FROM metrics WHERE research_id=?", (research_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def save_event(research_id: str, data: dict) -> None:
    with transaction() as conn:
        conn.execute(
            "INSERT INTO events (research_id, data, created_at) VALUES (?,?, datetime('now'))",
            (research_id, json.dumps(data)),
        )


def get_events(research_id: str) -> List[dict]:
    from app.storage.database import get_connection
    conn = get_connection()
    rows = conn.execute("SELECT data FROM events WHERE research_id=? ORDER BY id", (research_id,)).fetchall()
    return [json.loads(row["data"]) for row in rows]

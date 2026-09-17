"""Gradio Blocks UI (spec sections 25-34)."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import gradio as gr

from app.config import settings
from app.models.enums import ResearchStatus
from app.storage import repositories as repo
from app.services.research_manager import run_research

_STATE_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}

_EXPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "exports"
_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _format_progress(research_id: str) -> str:
    job = repo.get_job(research_id)
    if not job:
        return "No active research."
    lines = [f"Research ID: {research_id}", f"Status: {job.status.value.upper()}", ""]
    events = repo.get_events(research_id)[-12:]
    for e in events:
        mark = "✓" if e.get("success", True) is not False else "✗"
        detail = e.get("detail", "")
        lines.append(f"{mark} {e['event']}" + (f" — {detail}" if detail else ""))
    return "\n".join(lines)


def _format_plan(research_id: str) -> str:
    tasks = repo.get_tasks(research_id)
    if not tasks:
        return "No plan yet."
    lines = ["Research Plan", ""]
    status_icons = {"completed": "✓", "running": "→", "pending": "○", "failed": "✗", "retrying": "↻", "skipped": "-"}
    for i, t in enumerate(tasks, 1):
        icon = status_icons.get(t.status.value, "○")
        lines.append(f"{i}. {t.question}\n   Status: {t.status.value} {icon}")
    return "\n\n".join(lines)


def _format_sources(research_id: str) -> list[list]:
    sources = repo.get_sources(research_id)
    return [[s.title or s.url, s.publisher, s.source_type.value, f"{s.relevance_score*100:.0f}%", s.url] for s in sources]


def _format_evidence(research_id: str) -> str:
    evidence = repo.get_evidence(research_id)
    if not evidence:
        return "No evidence yet."
    blocks = []
    for e in evidence[:50]:
        blocks.append(f"Evidence {e.evidence_id}\nSource: {e.title or e.url}\nRelevance: {e.relevance_score*100:.0f}%\n\n{e.text}\n")
    return "\n---\n".join(blocks)


def _format_claims(research_id: str) -> str:
    claims = repo.get_claims(research_id)
    if not claims:
        return "No claims yet."
    status_labels = {
        "verified": "✓ VERIFIED", "partially_supported": "◐ PARTIALLY SUPPORTED",
        "contradicted": "✗ CONTRADICTED", "unsupported": "○ UNSUPPORTED", "pending": "… PENDING",
    }
    blocks = []
    for c in claims:
        label = status_labels.get(c.verification_status.value, c.verification_status.value)
        blocks.append(
            f"CLAIM {c.claim_id}\n\n{c.text}\n\nStatus: {label}\nConfidence: {c.confidence*100:.0f}%\n"
            f"Supporting evidence: {', '.join(c.supporting_evidence_ids) or 'none'}\n"
            f"Contradicting evidence: {', '.join(c.contradicting_evidence_ids) or 'none'}"
        )
    return "\n\n---\n\n".join(blocks)


def _format_metrics(research_id: str) -> str:
    m = repo.get_metrics(research_id)
    if not m:
        return "No metrics yet."
    return (
        f"Research duration:   {m['duration_seconds']:.1f} sec\n"
        f"LLM calls:           {m['llm_calls']}\n"
        f"Search calls:        {m['search_calls']}\n"
        f"Input tokens:        {m['input_tokens']:,}\n"
        f"Output tokens:       {m['output_tokens']:,}\n"
        f"Estimated cost:      ${m['estimated_cost']:.4f}\n\n"
        f"Sources discovered:  {m['sources_discovered']}\n"
        f"Sources selected:    {m['sources_selected']}\n"
        f"Evidence blocks:     {m['evidence_blocks']}\n"
        f"Claims generated:    {m['claims_generated']}\n"
        f"Claims verified:     {m['claims_verified']}\n"
        f"Claims unsupported:  {m['claims_unsupported']}"
    )


def _export_json(research_id: str) -> str:
    job = repo.get_job(research_id)
    if not job:
        return ""
    data = {
        "research_id": research_id,
        "question": job.question,
        "plan": [t.model_dump() for t in repo.get_tasks(research_id)],
        "claims": [c.model_dump() for c in repo.get_claims(research_id)],
        "sources": [s.model_dump() for s in repo.get_sources(research_id)],
        "report": job.report,
        "metrics": repo.get_metrics(research_id),
    }
    path = _EXPORTS_DIR / f"{research_id}_export.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return str(path)


def _export_markdown(research_id: str) -> str:
    job = repo.get_job(research_id)
    path = _EXPORTS_DIR / f"{research_id}_report.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(job.report or "")
    return str(path)


def start_research(question: str, depth: str, progress=gr.Progress()):
    if not question or not question.strip():
        yield "Please enter a research question.", "", [], "", "", "", "", None, None
        return

    result_holder = {}

    def _run():
        job = run_research(question, depth)
        result_holder["job"] = job

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    research_id_holder = {"id": None}
    while thread.is_alive() or "id" not in research_id_holder or research_id_holder["id"] is None:
        if research_id_holder["id"] is None:
            # Best-effort: find the most recently created job for this question.
            pass
        import time as _t
        _t.sleep(0.4)
        # Discover research_id via the latest job row once created.
        if research_id_holder["id"] is None:
            latest = _find_latest_research_id()
            if latest:
                research_id_holder["id"] = latest
        rid = research_id_holder["id"]
        if rid:
            job = repo.get_job(rid)
            yield (
                _format_progress(rid),
                _format_plan(rid),
                _format_sources(rid),
                _format_evidence(rid),
                _format_claims(rid),
                job.report or "_Report will appear here once synthesis completes._",
                _format_metrics(rid),
                rid,
                rid,
            )
            if job and job.status in (ResearchStatus.COMPLETED, ResearchStatus.FAILED):
                break
        if not thread.is_alive():
            break

    thread.join(timeout=1)


def _find_latest_research_id() -> str | None:
    from app.storage.database import get_connection
    conn = get_connection()
    row = conn.execute("SELECT id FROM research_jobs ORDER BY created_at DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Deep Research Agent") as demo:
        gr.Markdown("# 🔎 DEEP RESEARCH AGENT\nEvidence-based autonomous research assistant")

        with gr.Row():
            question_box = gr.Textbox(
                label="Research Question", lines=4,
                placeholder=(
                    "Ask a complex research question...\n\n"
                    "Example:\nHow would a prolonged disruption in the Strait of Hormuz "
                    "affect India's economy, inflation and crude oil prices?"
                ),
            )
        with gr.Row():
            depth_dropdown = gr.Dropdown(choices=list(settings.depth_presets.keys()), value="Standard", label="Research Depth")
            start_btn = gr.Button("START RESEARCH", variant="primary")

        research_id_state = gr.State(value=None)
        export_id_state = gr.State(value=None)

        with gr.Row():
            progress_box = gr.Textbox(label="Research Progress", lines=10, interactive=False)
            plan_box = gr.Textbox(label="Research Plan", lines=10, interactive=False)

        report_box = gr.Markdown(label="Final Report", value="_Report will appear here once synthesis completes._")

        with gr.Tab("Sources"):
            sources_table = gr.Dataframe(headers=["Title", "Publisher", "Type", "Relevance", "URL"], interactive=False)
        with gr.Tab("Evidence"):
            evidence_box = gr.Textbox(lines=15, interactive=False)
        with gr.Tab("Claims"):
            claims_box = gr.Textbox(lines=15, interactive=False)
        with gr.Tab("Metrics"):
            metrics_box = gr.Textbox(lines=12, interactive=False)

        with gr.Row():
            export_md_btn = gr.Button("Download Markdown")
            export_json_btn = gr.Button("Download JSON")
            md_file = gr.File(label="Markdown export", visible=True)
            json_file = gr.File(label="JSON export", visible=True)

        start_btn.click(
            fn=start_research,
            inputs=[question_box, depth_dropdown],
            outputs=[progress_box, plan_box, sources_table, evidence_box, claims_box, report_box, metrics_box, research_id_state, export_id_state],
        )
        export_md_btn.click(fn=_export_markdown, inputs=[export_id_state], outputs=[md_file])
        export_json_btn.click(fn=_export_json, inputs=[export_id_state], outputs=[json_file])

    return demo


def launch():
    demo = build_app()
    demo.queue().launch()

# Deep Research Agent (V1)

An AI-powered research system that turns a complex research question into a structured, evidence-backed, cited report.

Built following the design principle: **use an LLM for reasoning; use deterministic software for everything that should be reliable and reproducible** (state transitions, retries, timeouts, persistence, citation validation).

## Architecture

```
Gradio UI → Research Manager (state machine) → Planner Agent → Research Workers (search/rank/extract)
          → Verifier Agent → Synthesizer Agent → Citation Validator → Final Report
```

See [Deep Research Agent — Technical Requirements & Implementation Specification.md](Deep%20Research%20Agent%20%E2%80%94%20Technical%20Requirements%20%26%20Implementation%20Specification.md) for the full spec this implementation follows.

Repository layout mirrors section 36 of the spec: `app/agents`, `app/tools`, `app/models`, `app/services`, `app/storage`, `app/ui`, `prompts/`, `evals/`, `tests/`.

## Setup

```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then fill in LLM_API_KEY
```

Search works out of the box via DuckDuckGo (no API key). Set `SEARCH_PROVIDER=tavily` and `TAVILY_API_KEY` to use Tavily instead.

## Run

```powershell
python -m app.main
```

Opens the Gradio app at http://127.0.0.1:7860. Enter a research question, pick a depth (Quick/Standard/Deep), and click **Start Research**.

## Run tests

```powershell
pytest tests -q
```

## Run evaluation

```powershell
python -m evals.evaluator
```

Runs the golden dataset (`evals/dataset.json`) through the full pipeline and writes deterministic + LLM-judge scores to `evals/results/latest.json`.

## Key design decisions

- **Pydantic everywhere** for LLM outputs (plan, candidate claims, verification result) — never trust raw JSON.
- **Deterministic source ranking** (spec §22): government/academic sources score higher, duplicates are penalized via `content_hash`.
- **Verifier answers "does the evidence support this claim?"**, not "is this true?" — avoids compounding hallucination.
- **Citation validator** strips any citation marker in the final report that doesn't map to a real, persisted source.
- **SQLite repository layer** (`app/storage`) isolates persistence so swapping to PostgreSQL later doesn't touch business logic.
- **Bounded retries + per-task isolation**: a failing search task doesn't fail the whole research job; the manager degrades gracefully.
- **Cost/latency accounting** on every LLM call, surfaced in the Metrics tab.

## What's intentionally out of scope for V1

Kafka, Kubernetes, Celery, distributed workers, auth, vector search infra — see spec §4 and §49-57 for the production roadmap these would belong to.

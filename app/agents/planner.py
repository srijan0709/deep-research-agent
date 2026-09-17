"""Planning Agent (spec section 7.1)."""
from __future__ import annotations

from app.agents.prompt_loader import load_prompt
from app.models.research import ResearchPlan
from app.tools.llm_client import LLMCallResult, call_structured


def generate_plan(question: str, num_tasks: int) -> tuple[ResearchPlan, LLMCallResult]:
    system_prompt = load_prompt("planner_v1.txt")
    user_prompt = (
        f"Research question:\n{question}\n\n"
        f"Produce between 1 and {num_tasks} tasks (aim for exactly {num_tasks} if the question warrants it)."
    )
    plan, metrics = call_structured(system_prompt, user_prompt, ResearchPlan)
    # Deterministic enforcement of limits regardless of what the LLM returned.
    plan.tasks = plan.tasks[:num_tasks]
    return plan, metrics

"""Deterministic wrapper around the LLM provider.

The application code (this module) owns retries, timeouts, structured-output
validation and token accounting. The LLM itself is only responsible for
producing the reasoning content asked of it.
"""
from __future__ import annotations

import json
import time
from typing import Optional, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_model_pricing, settings

T = TypeVar("T", bound=BaseModel)

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        kwargs = {"api_key": settings.llm_api_key or "sk-placeholder"}
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        _client = OpenAI(**kwargs, timeout=settings.llm_timeout_seconds)
    return _client


class LLMCallResult(BaseModel):
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0


@retry(stop=stop_after_attempt(settings.max_retries), wait=wait_exponential(multiplier=1, min=1, max=10))
def _chat_completion(messages: list[dict], model: str, response_format: Optional[dict] = None) -> LLMCallResult:
    client = get_client()
    start = time.perf_counter()
    kwargs = {"model": model, "messages": messages}
    if response_format:
        kwargs["response_format"] = response_format
    response = client.chat.completions.create(**kwargs)
    latency_ms = (time.perf_counter() - start) * 1000
    choice = response.choices[0]
    usage = response.usage
    return LLMCallResult(
        content=choice.message.content or "",
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        latency_ms=latency_ms,
    )


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = get_model_pricing(model)
    return (input_tokens / 1000.0) * pricing["input"] + (output_tokens / 1000.0) * pricing["output"]


def call_structured(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    model: Optional[str] = None,
) -> tuple[T, LLMCallResult]:
    """Call the LLM and validate the JSON response against a Pydantic schema.

    Raises pydantic.ValidationError if the model output doesn't conform;
    callers should decide whether to retry with a repair prompt.
    """
    model = model or settings.llm_model
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    result = _chat_completion(messages, model, response_format={"type": "json_object"})
    data = json.loads(result.content)
    parsed = schema.model_validate(data)
    return parsed, result


def call_text(system_prompt: str, user_prompt: str, model: Optional[str] = None) -> LLMCallResult:
    model = model or settings.llm_model
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return _chat_completion(messages, model)

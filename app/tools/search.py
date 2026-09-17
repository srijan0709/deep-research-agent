"""Web search tool.

Provides `search_web(query, max_results)` with a normalized, typed result
regardless of the underlying provider. Defaults to DuckDuckGo (no API key
required) so the project is runnable out of the box; set SEARCH_PROVIDER and
TAVILY_API_KEY to use Tavily instead.
"""
from __future__ import annotations

import hashlib
from typing import List

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings


class SearchResult(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""
    publisher: str = ""


def _content_hash(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}|{title}".encode("utf-8", errors="ignore")).hexdigest()[:16]


@retry(stop=stop_after_attempt(settings.max_retries), wait=wait_exponential(multiplier=1, min=1, max=8))
def _search_duckduckgo(query: str, max_results: int) -> List[SearchResult]:
    from duckduckgo_search import DDGS

    results: List[SearchResult] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            url = item.get("href") or item.get("url") or ""
            title = item.get("title", "")
            snippet = item.get("body", "")
            if not url:
                continue
            results.append(SearchResult(url=url, title=title, snippet=snippet, publisher=_publisher_from_url(url)))
    return results


@retry(stop=stop_after_attempt(settings.max_retries), wait=wait_exponential(multiplier=1, min=1, max=8))
def _search_tavily(query: str, max_results: int) -> List[SearchResult]:
    import httpx

    resp = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": settings.tavily_api_key, "query": query, "max_results": max_results},
        timeout=settings.search_timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("results", []):
        url = item.get("url", "")
        title = item.get("title", "")
        results.append(SearchResult(
            url=url, title=title, snippet=item.get("content", ""),
            publisher=_publisher_from_url(url),
        ))
    return results


def _publisher_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "")
    except Exception:
        return ""


def search_web(query: str, max_results: int = 8) -> List[SearchResult]:
    """Structured tool call: query -> normalized search results.

    Raises on persistent failure after retries; caller (research worker) is
    responsible for bounded retry/skip semantics at the task level.
    """
    if settings.search_provider == "tavily" and settings.tavily_api_key:
        return _search_tavily(query, max_results)
    return _search_duckduckgo(query, max_results)


def content_hash_for(url: str, title: str) -> str:
    return _content_hash(url, title)

"""Citation validation service (spec section 15).

Ensures every citation marker used in the generated report maps back to a
real, known source, and drops/flags markers that don't.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from app.models.source import Source


@dataclass
class CitationValidationResult:
    valid_report: str
    used_markers: List[int]
    invalid_markers: List[int]


_MARKER_RE = re.compile(r"\[(\d+)\]")


def validate_citations(report: str, citation_map: dict[str, int], sources: List[Source]) -> CitationValidationResult:
    valid_numbers = set(citation_map.values())
    used = sorted({int(m) for m in _MARKER_RE.findall(report)})
    invalid = [n for n in used if n not in valid_numbers]

    cleaned = report
    for n in invalid:
        # Remove citation markers that don't correspond to a known source
        # rather than let an unverifiable citation reach the user.
        cleaned = re.sub(rf"\[{n}\]", "", cleaned)

    return CitationValidationResult(
        valid_report=cleaned,
        used_markers=[n for n in used if n not in invalid],
        invalid_markers=invalid,
    )

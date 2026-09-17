from app.models.source import Source
from app.services.citation_service import validate_citations


def _make_source(source_id: str, url: str) -> Source:
    return Source(source_id=source_id, research_id="r1", url=url, title="Title", content_hash="h1")


def test_validate_citations_keeps_known_markers():
    sources = [_make_source("src_1", "https://a.com"), _make_source("src_2", "https://b.com")]
    citation_map = {"src_1": 1, "src_2": 2}
    report = "Some claim [1]. Another claim [2]."

    result = validate_citations(report, citation_map, sources)

    assert result.used_markers == [1, 2]
    assert result.invalid_markers == []
    assert "[1]" in result.valid_report


def test_validate_citations_strips_unknown_markers():
    sources = [_make_source("src_1", "https://a.com")]
    citation_map = {"src_1": 1}
    report = "Some claim [1]. A fabricated claim [7]."

    result = validate_citations(report, citation_map, sources)

    assert result.invalid_markers == [7]
    assert "[7]" not in result.valid_report
    assert "[1]" in result.valid_report

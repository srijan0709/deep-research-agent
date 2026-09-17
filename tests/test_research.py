from app.services.research_manager import _now_iso


def test_now_iso_format():
    value = _now_iso()
    assert "T" in value
    assert value.endswith("+00:00") or "Z" in value

from pathlib import Path

def test_single_rank_accordion_controller_present():
    html = Path("docs/index.html").read_text(encoding="utf-8")
    assert "ml-rank-accordion-single-controller" in html
    assert "ml-rank-badge" in html
    assert "bindClickOnce" in html
    assert "convertDetailsToCards" in html
    assert "ml-accordion-div-controller" not in html
    assert "ml-rank-badge-nonintrusive-fix" not in html
    assert "ml-accordion-rank-stable" not in html

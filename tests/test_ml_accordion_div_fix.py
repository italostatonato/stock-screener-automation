from pathlib import Path

def test_ml_accordion_div_controller_present():
    html = Path("docs/index.html").read_text(encoding="utf-8")
    assert "ml-accordion-div-controller" in html
    assert "ml-acc-card" in html
    assert "ml-acc-head" in html
    assert "ml-accordion-collapse-fix" not in html
    assert "ml-accordion-manual-controller" not in html

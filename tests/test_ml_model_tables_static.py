from pathlib import Path

def test_static_ml_model_section_present():
    html = Path("docs/index.html").read_text(encoding="utf-8")
    assert "staticMlModelByModelSection" in html
    assert "staticMlModelTables" in html
    assert "static-ml-model-tables-renderer" in html
    assert "Top 20 por modelo" in html
    assert "Como cada modelo funciona" in html

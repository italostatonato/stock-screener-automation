from pathlib import Path

def test_ml_performance_rank_enhancer_present():
    html = Path("docs/index.html").read_text(encoding="utf-8")
    assert "ml-performance-rank-enhancer" in html
    assert "mlPerformanceRankNote" in html
    assert "ml-rank-badge" in html
    assert "Ranking de performance" in html or "Ranking:" in html

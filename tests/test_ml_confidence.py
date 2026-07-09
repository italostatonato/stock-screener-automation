import json
from pathlib import Path

from src.ml_confidence import (
    add_confidence_to_performance_records,
    build_ml_confidence_summary,
)


def test_confidence_zero_when_no_valid_windows(tmp_path: Path):
    docs = tmp_path / "docs" / "data"
    docs.mkdir(parents=True)
    (docs / "index.json").write_text(json.dumps(["2026-06-21", "2026-07-08"]), encoding="utf-8")

    performance = [
        {
            "Tipo": "ACAO",
            "Modelo": "Random Forest",
            "Horizonte": "30d",
            "Janelas_Validas": 0,
            "Hit_Rate_Top20": None,
            "Spearman_IC": None,
            "Alpha_vs_Score_Top": None,
        }
    ]

    summary = build_ml_confidence_summary(performance, docs_data_dir=docs, horizon_days=30)

    assert summary["status"] == "Aquecendo"
    assert summary["confiabilidade_preditiva_pct"] == 0.0
    assert summary["maturidade_dados_pct"] > 0
    assert summary["modelo_mais_confiavel"] is None


def test_confidence_positive_with_valid_windows(tmp_path: Path):
    docs = tmp_path / "docs" / "data"
    docs.mkdir(parents=True)
    (docs / "index.json").write_text(json.dumps(["2026-06-01", "2026-07-15"]), encoding="utf-8")

    performance = [
        {
            "Tipo": "ACAO",
            "Modelo": "XGBoost",
            "Horizonte": "30d",
            "Janelas_Validas": 8,
            "Hit_Rate_Top20": 0.61,
            "Spearman_IC": 0.18,
            "Alpha_vs_Score_Top": 0.012,
        }
    ]

    summary = build_ml_confidence_summary(performance, docs_data_dir=docs, horizon_days=30)

    assert summary["status"] == "Ativo"
    assert summary["confiabilidade_preditiva_pct"] > 0
    assert summary["modelo_mais_confiavel"]["Modelo"] == "XGBoost"


def test_enrich_performance_records_adds_columns(tmp_path: Path):
    docs = tmp_path / "docs" / "data"
    docs.mkdir(parents=True)
    (docs / "index.json").write_text(json.dumps(["2026-06-01", "2026-07-15"]), encoding="utf-8")

    performance = [
        {
            "Tipo": "FII",
            "Modelo": "Score Top",
            "Horizonte": "30d",
            "Janelas_Validas": 6,
            "Hit_Rate_Top20": 0.55,
            "Spearman_IC": 0.08,
            "Alpha_vs_Score_Top": 0.0,
        }
    ]
    summary = build_ml_confidence_summary(performance, docs_data_dir=docs)
    enriched = add_confidence_to_performance_records(performance, summary)

    assert "Confiabilidade_Pct" in enriched[0]
    assert "Nivel_Confiabilidade" in enriched[0]

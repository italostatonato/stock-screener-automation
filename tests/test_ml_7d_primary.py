from pathlib import Path
import json
import pandas as pd


def test_ml_7d_outputs_exist():
    ml = Path("data/ml")
    assert (ml / "dataset_acoes.parquet").exists()
    assert (ml / "dataset_fiis.parquet").exists()
    assert (ml / "model_predictions_acoes.parquet").exists()
    assert (ml / "model_predictions_fiis.parquet").exists()


def test_7d_has_more_targets_than_30d():
    acoes = pd.read_parquet("data/ml/dataset_acoes.parquet")
    fiis = pd.read_parquet("data/ml/dataset_fiis.parquet")
    valid_7d = pd.to_numeric(acoes.get("Retorno_Futuro_7d"), errors="coerce").notna().sum() + pd.to_numeric(fiis.get("Retorno_Futuro_7d"), errors="coerce").notna().sum()
    valid_30d = pd.to_numeric(acoes.get("Retorno_Futuro_30d"), errors="coerce").notna().sum() + pd.to_numeric(fiis.get("Retorno_Futuro_30d"), errors="coerce").notna().sum()
    assert valid_7d > valid_30d


def test_dashboard_uses_7d_as_primary():
    idx = json.loads(Path("docs/data/index.json").read_text(encoding="utf-8"))
    latest = sorted(idx)[-1]
    payload = json.loads(Path(f"docs/data/{latest}.json").read_text(encoding="utf-8"))
    ml = payload.get("modelos_ml", {})
    assert ml.get("horizonte_principal") == "7d"
    assert ml.get("horizonte_estrategico") == "30d"

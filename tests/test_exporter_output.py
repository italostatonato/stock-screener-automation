import json

import pandas as pd
import pytest

from src.exporter import export_dashboard_json


def test_export_uses_custom_directories_and_does_not_truncate_snapshot_on_error(tmp_path):
    data_dir = tmp_path / "custom-data"
    ml_dir = data_dir / "ml"
    ml_dir.mkdir(parents=True)
    pd.DataFrame({
        "Data_Execucao": ["2026-01-02"], "Ticker": ["CUSTOM3"],
        "Tipo": ["ACAO"], "Horizonte": ["7d"], "score_top": [70.0],
    }).to_parquet(ml_dir / "model_predictions_acoes.parquet", index=False)
    output = tmp_path / "web"
    fiis = pd.DataFrame({"FUNDOS": ["TEST11"], "PREÇO ATUAL (R$)": [10.0]})
    acoes = pd.DataFrame({"Ação": ["CUSTOM3"], "Preço": [20.0]})
    kwargs = dict(output_dir=str(output), data_hoje="2026-01-02", top_fiis=fiis,
                  top_acoes=acoes, data_dir=str(data_dir))
    export_dashboard_json(**kwargs, market_data=None)
    path = output / "2026-01-02.json"
    before = path.read_bytes()
    payload = json.loads(before)
    assert payload["modelos_ml"]["ranking"]["acoes"][0]["Ticker"] == "CUSTOM3"
    assert payload["modelos_ml"]["confiabilidade"]["qtd_snapshots"] == 0
    with pytest.raises(ValueError, match="JSON compliant"):
        export_dashboard_json(**kwargs, market_data={"cambio": {"invalid": float("nan")}})
    assert path.read_bytes() == before
    assert not (output / "2026-01-02.json.tmp").exists()

import pandas as pd

from src.exporter import _apply_ml_prediction_guardrails, _model_performance_history_records, _latest_records_from_predictions


def test_ranking_rejects_old_date_and_different_horizon(tmp_path):
    path = tmp_path / "predictions.parquet"
    pd.DataFrame({
        "Data_Execucao": ["2026-01-01", "2026-01-02", "2026-01-02"],
        "Ticker": ["OLD3", "MONTH3", "WEEK3"],
        "Horizonte": ["7d", "30d", "7d"], "score_top": [70, 80, 60],
    }).to_parquet(path, index=False)
    records = _latest_records_from_predictions(str(path), data_hoje="2026-01-02")
    assert [r["Ticker"] for r in records] == ["WEEK3"]


def test_expected_return_uses_ensemble_validation():
    records = [{"Tipo": "ACAO", "Horizonte": "7d", "modelo_lider": "Ridge",
                "modelo_projecao": "Ensemble", "retorno_esperado_7d": 0.03}]
    performance = [{"Tipo": "ACAO", "Modelo": "Ridge", "Horizonte": "7d", "Janelas_Validas": 10}]
    result = _apply_ml_prediction_guardrails(records, performance)[0]
    assert result["projecao_confiavel"] is False
    assert result["janelas_validas_modelo"] == 0


def test_warmup_does_not_fall_back_to_different_horizon():
    row = {"Horizonte": "7d", "retorno_esperado_7d": None, "retorno_esperado_30d": 0.5}
    result = _apply_ml_prediction_guardrails([row], [])[0]
    assert result["retorno_esperado_horizonte"] == "7d"
    assert result["retorno_esperado_exibicao"] is None


def test_model_performance_history_preserva_janela_e_calcula_alpha(tmp_path):
    tickers = [f"TEST{i:02d}" for i in range(25)]
    predictions = pd.DataFrame({
        "Data_Execucao": ["2026-01-02"] * 25,
        "Ticker": tickers,
        "score_top": list(range(25)),
        "score_ridge": list(reversed(range(25))),
        "Horizonte": ["7d"] * 25,
    })
    dataset = pd.DataFrame({
        "Data_Execucao": ["2026-01-02"] * 25,
        "Ação": tickers,
        "Retorno_Futuro_7d": [value / 100 for value in range(25)],
        "Data_Futura_7d": ["2026-01-09"] * 25,
    })
    predictions_path = tmp_path / "predictions.parquet"
    dataset_path = tmp_path / "dataset.parquet"
    predictions.to_parquet(predictions_path, index=False)
    dataset.to_parquet(dataset_path, index=False)

    records = _model_performance_history_records(
        str(predictions_path),
        str(dataset_path),
        tipo="ACAO",
        ticker_col="Ação",
        horizon=7,
    )

    by_model = {row["Modelo"]: row for row in records}
    assert set(by_model) == {"Score Top", "Ridge"}
    assert by_model["Score Top"]["Data_Referencia"] == "2026-01-02"
    assert by_model["Score Top"]["Data_Resultado"] == "2026-01-09"
    assert by_model["Score Top"]["Ativos_Top20"] == 20
    assert by_model["Score Top"]["Alpha_vs_Score_Top"] == 0.0
    assert by_model["Ridge"]["Alpha_vs_Score_Top"] < 0


def test_ml_guardrail_oculta_projecao_com_amostra_insuficiente():
    records = [{
        "Tipo": "ACAO",
        "Ticker": "TEST3",
        "modelo_lider": "Ridge",
        "retorno_esperado_30d": 0.18,
    }]
    performance = [{
        "Tipo": "ACAO",
        "Modelo": "Ridge",
        "Horizonte": "30d",
        "Janelas_Validas": 1,
    }]

    guarded = _apply_ml_prediction_guardrails(records, performance)[0]

    assert guarded["projecao_confiavel"] is False
    assert guarded["retorno_esperado_exibicao"] is None
    assert guarded["janelas_validas_modelo"] == 1
    assert "1 de 3" in guarded["motivo_projecao"]


def test_ml_guardrail_oculta_outlier_mesmo_com_historico():
    records = [{
        "Tipo": "FII",
        "Ticker": "TEST11",
        "modelo_lider": "XGBoost",
        "retorno_esperado_30d": 1.62,
    }]
    performance = [{
        "Tipo": "FII",
        "Modelo": "XGBoost",
        "Horizonte": "30d",
        "Janelas_Validas": 10,
    }]

    guarded = _apply_ml_prediction_guardrails(records, performance)[0]

    assert guarded["projecao_confiavel"] is False
    assert guarded["projecao_outlier"] is True
    assert guarded["retorno_esperado_exibicao"] is None

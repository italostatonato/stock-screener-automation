import numpy as np
import pandas as pd

from src import ml_models
from src.ml_horizons import prediction_horizons, predictions_for_horizon


def test_preserva_previsoes_de_dois_horizontes_no_mesmo_dia(tmp_path):
    path = str(tmp_path / "predictions.parquet")
    base = {"Data_Execucao": "2026-01-01", "Tipo": "ACAO", "Ticker": "TEST3", "score_top": 70}
    ml_models._append_predictions(pd.DataFrame([{**base, "retorno_esperado_30d": 0.1}]), path)
    result = ml_models._append_predictions(pd.DataFrame([{**base, "Horizonte": "7d", "retorno_esperado_7d": 0.02}]), path)
    assert len(result) == 2
    assert set(result["Horizonte"]) == {"7d", "30d"}


def test_score_de_30d_nao_pode_ser_avaliado_como_7d():
    frame = pd.DataFrame({"Data_Execucao": ["2026-01-01"] * 2, "Ticker": ["A", "B"],
                          "score_top": [80, 90], "score_ridge": [10, 20],
                          "retorno_esperado_30d": [0.2, 0.3]})
    result = predictions_for_horizon(frame, 7)
    assert result["score_ridge"].isna().all()
    assert result["score_top"].tolist() == [80, 90]
    assert prediction_horizons(frame).tolist() == ["30d", "30d"]


def test_treino_exclui_targets_que_ainda_nao_estavam_disponiveis(monkeypatch):
    trained = []

    class Model:
        def fit(self, x, y):
            trained.extend(y.tolist())

        def predict(self, x):
            return np.zeros(len(x))

    monkeypatch.setattr(ml_models, "MIN_TRAIN_ROWS", 1)
    monkeypatch.setattr(ml_models, "_model_factories", lambda: {"score_ridge": Model})
    frame = pd.DataFrame({
        "Ação": ["TEST3"] * 3, "Data_Execucao": ["2026-01-01", "2026-01-02", "2026-01-09"],
        "Preço": [10, 11, 12], "Score": [60, 65, 70],
        "Retorno_Futuro_7d": [0.1, 0.9, np.nan],
        "Data_Futura_7d": ["2026-01-08", "2026-01-12", None],
    })
    result = ml_models._train_predict_models(frame, ml_models.SPECS["acoes"], 7)
    assert trained == [0.1]
    assert result["Horizonte"].tolist() == ["7d"]
    assert result["modelo_projecao"].tolist() == ["Ensemble"]

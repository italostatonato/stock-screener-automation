import pandas as pd
import pytest

from src.dataset_builder import _add_basic_features, _add_future_returns, _prepare_base, build_ml_dataset


def test_invalid_source_cannot_silently_reuse_old_dataset(tmp_path):
    output = tmp_path / "dataset.parquet"
    pd.DataFrame({"old": [1]}).to_parquet(output, index=False)
    before = output.read_bytes()
    with pytest.raises(ValueError, match="histórico"):
        build_ml_dataset(str(tmp_path / "missing.parquet"), str(output),
                         "Ticker", "Data", "Preco", "TEST")
    assert output.read_bytes() == before


def test_top_rank_e_aprovado_fora_top_sao_elegiveis():
    source = pd.DataFrame({
        "Ticker": ["A", "B", "C"], "Data": pd.to_datetime(["2026-01-01"] * 3),
        "Preco": [10, 10, 10], "Status": ["Rank #1", "Aprovado (fora do Top N)", "Eliminado no filtro fixo"],
    })
    result = _add_basic_features(source, "Ticker", "Data", "Preco")
    assert result["Aprovado_Filtro"].tolist() == [1, 1, 0]


def test_preparacao_descarta_ticker_ausente_e_preco_invalido():
    source = pd.DataFrame({
        "Ticker": [None, "", "A", "B", "C", "D"],
        "Data": ["2026-01-01"] * 6, "Preco": [10, 10, 0, -1, float("inf"), 12.5],
    })
    result = _prepare_base(source, "Ticker", "Data", "Preco")
    assert result["Ticker"].tolist() == ["D"]


def test_horizontes_iteraveis_buscam_primeiro_snapshot_posterior():
    source = pd.DataFrame({"Ticker": ["A"] * 3,
                           "Data": pd.to_datetime(["2026-01-01", "2026-01-09", "2026-02-02"]),
                           "Preco": [100.0, 110.0, 120.0]})
    result = _add_future_returns(source, "Ticker", "Data", "Preco", iter([7, 30]))
    assert result.loc[0, "Data_Futura_7d"] == pd.Timestamp("2026-01-09")
    assert result.loc[0, "Data_Futura_30d"] == pd.Timestamp("2026-02-02")

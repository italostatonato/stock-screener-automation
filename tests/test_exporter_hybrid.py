import pandas as pd
import pytest

from src.exporter import _build_hybrid_portfolio


def _records(start, end):
    return [
        {"data": "2026-01-02", "valor": start},
        {"data": "2026-01-09", "valor": end},
    ]


def _benchmark(start, end):
    return pd.DataFrame({
        "data": pd.to_datetime(["2026-01-02", "2026-01-09"]),
        "valor": [start, end],
    })


def test_build_hybrid_portfolio_aplica_pesos_e_contribuicoes():
    result = _build_hybrid_portfolio(
        acoes_series=_records(100, 110),
        fiis_series=_records(100, 104),
        benchmarks={
            "CDI": _benchmark(100, 101),
            "IVVB11": _benchmark(100, 120),
            "IFIX": _benchmark(100, 103),
            "IPCA": _benchmark(100, 100.5),
        },
        top_acoes=pd.DataFrame({"Ação": ["ABCD3", "EFGH4"]}),
        top_fiis=pd.DataFrame({"FUNDOS": ["XPTO11", "TEST11"]}),
    )

    assert result["disponivel"] is True
    assert result["serie"][-1]["valor"] == pytest.approx(108.2)
    assert sum(item["contribuicao_pct"] for item in result["componentes"]) == pytest.approx(8.2)
    assert set(result["comparativos"]) == {
        "CDI", "IFIX", "Top 20 FIIs", "Top 20 Ações BR", "IPCA"
    }
    assert result["ativos"]["acoes_top20"]["peso_por_ativo_pct"] == pytest.approx(20.0)
    assert result["ativos"]["fiis_top20"]["peso_por_ativo_pct"] == pytest.approx(12.5)


def test_build_hybrid_portfolio_exige_ivvb11():
    result = _build_hybrid_portfolio(
        acoes_series=_records(100, 110),
        fiis_series=_records(100, 104),
        benchmarks={"CDI": _benchmark(100, 101)},
        top_acoes=pd.DataFrame(),
        top_fiis=pd.DataFrame(),
    )

    assert result["disponivel"] is False
    assert "IVVB11" in result["motivo"]
    assert result["serie"] == []

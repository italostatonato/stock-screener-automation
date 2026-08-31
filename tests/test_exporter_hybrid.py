import pandas as pd
import pytest

from src.exporter import (
    _base100_records_from_date,
    _build_hybrid_portfolio,
    _build_portfolio_base100_from_history,
)


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
    assert result["serie"][-1]["valor"] == pytest.approx(108.4)
    assert sum(item["contribuicao_pct"] for item in result["componentes"]) == pytest.approx(8.4)
    assert set(result["comparativos"]) == {
        "CDI", "IFIX", "Top 20 FIIs", "Top 20 Ações BR", "IPCA"
    }
    assert result["ativos"]["acoes_top20"]["peso_por_ativo_pct"] == pytest.approx(15.0)
    assert result["ativos"]["fiis_top20"]["peso_por_ativo_pct"] == pytest.approx(15.0)


def test_build_hybrid_portfolio_rebalanceia_pesos_em_cada_periodo():
    three_dates = ["2026-01-02", "2026-01-09", "2026-01-16"]

    def records(values):
        return [
            {"data": date, "valor": value}
            for date, value in zip(three_dates, values)
        ]

    def benchmark(values):
        return pd.DataFrame({
            "data": pd.to_datetime(three_dates),
            "valor": values,
        })

    result = _build_hybrid_portfolio(
        acoes_series=records([100, 110, 99]),
        fiis_series=records([100, 100, 100]),
        benchmarks={
            "CDI": benchmark([100, 100, 100]),
            "IVVB11": benchmark([100, 100, 100]),
        },
        top_acoes=pd.DataFrame({"Ação": ["ABCD3"]}),
        top_fiis=pd.DataFrame({"FUNDOS": ["XPTO11"]}),
    )

    # +3% na primeira semana e -3% sobre o novo patrimônio na segunda.
    assert result["serie"][-1]["valor"] == pytest.approx(99.91)
    action = next(item for item in result["componentes"] if item["chave"] == "acoes_top20")
    assert action["contribuicao_pct"] == pytest.approx(-0.09)
    assert action["contribuicao_serie"][-1]["valor"] == pytest.approx(-0.09)


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


def test_base100_rejeita_benchmark_com_apenas_um_ponto():
    single = pd.DataFrame({
        "data": pd.to_datetime(["2026-01-09"]),
        "valor": [123.0],
    })

    assert _base100_records_from_date(single, pd.Timestamp("2026-01-02")) == []


def test_top20_usa_composicao_de_cada_data_no_intervalo_seguinte(tmp_path):
    carteira_path = tmp_path / "carteiras.parquet"
    historico_path = tmp_path / "historico.parquet"
    pd.DataFrame({
        "Data_Carteira": ["2026-01-02", "2026-01-09", "2026-01-16"],
        "Tipo": ["ACAO", "ACAO", "ACAO"],
        "Ticker": ["ANTIGA3", "NOVA3", "NOVA3"],
    }).to_parquet(carteira_path, index=False)
    pd.DataFrame({
        "Data_Execucao": [
            "2026-01-02", "2026-01-02",
            "2026-01-09", "2026-01-09",
            "2026-01-16", "2026-01-16",
        ],
        "Ação": ["ANTIGA3", "NOVA3"] * 3,
        "Preço": [100, 50, 110, 50, 220, 60],
    }).to_parquet(historico_path, index=False)

    result = _build_portfolio_base100_from_history(
        tipo="ACAO",
        carteira_path=str(carteira_path),
        historico_path=str(historico_path),
        ticker_col="Ação",
        price_col="Preço",
    )

    # Primeira semana usa ANTIGA3 (+10%); a seguinte já usa NOVA3 (+20%).
    assert [row["valor"] for row in result] == pytest.approx([100.0, 110.0, 132.0])

    without_partial_snapshot = _build_portfolio_base100_from_history(
        tipo="ACAO",
        carteira_path=str(carteira_path),
        historico_path=str(historico_path),
        ticker_col="Ação",
        price_col="Preço",
        rebalance_dates=pd.to_datetime(["2026-01-02", "2026-01-16"]),
    )

    # Se 09/01 fosse um snapshot parcial, a troca para NOVA3 seria ignorada.
    assert [row["valor"] for row in without_partial_snapshot] == pytest.approx([100.0, 220.0])

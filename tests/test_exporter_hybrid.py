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


@pytest.mark.parametrize("extra_rows, expected_value, expected_reference", [
    ([], 101.0, "2026-10-23"),
    ([("2026-10-26", 102.0)], 102.0, "2026-10-26"),
    ([("2026-10-27", 999.0)], 101.0, "2026-10-23"),
])
def test_hybrid_cdi_usa_ultima_observacao_sem_projetar_ou_antecipar(
    extra_rows, expected_value, expected_reference
):
    dates = ["2026-10-19", "2026-10-26"]
    acoes = [{"data": date, "valor": value} for date, value in zip(dates, [100, 110])]
    fiis = [{"data": date, "valor": value} for date, value in zip(dates, [100, 104])]
    cdi_rows = [("2026-10-19", 100.0), ("2026-10-23", 101.0)] + extra_rows
    cdi = pd.DataFrame(cdi_rows, columns=["data", "valor"])
    cdi["data"] = pd.to_datetime(cdi["data"])
    original_cdi = cdi.copy(deep=True)
    original_acoes = [row.copy() for row in acoes]
    result = _build_hybrid_portfolio(
        acoes_series=acoes, fiis_series=fiis,
        benchmarks={
            "CDI": cdi,
            "IVVB11": pd.DataFrame({"data": pd.to_datetime(dates), "valor": [100, 120]}),
        },
        top_acoes=pd.DataFrame(), top_fiis=pd.DataFrame(),
    )

    assert result["disponivel"] is True
    assert result["fim"] == "2026-10-26"
    assert [row["data"] for row in result["serie"]] == dates
    cdi_component = next(item for item in result["componentes"] if item["chave"] == "cdi")
    assert cdi_component["serie"][-1] == {
        "data": "2026-10-26", "valor": expected_value,
        "data_referencia": expected_reference,
    }
    assert cdi_component["retorno_pct"] == pytest.approx(expected_value - 100)
    assert result["comparativos"]["CDI"] == cdi_component["serie"]
    expected_return = 0.3 * 10 + 0.3 * 4 + 0.2 * 20 + 0.2 * (expected_value - 100)
    assert result["serie"][-1]["valor"] == pytest.approx(100 + expected_return)
    assert sum(item["contribuicao_pct"] for item in result["componentes"]) == pytest.approx(expected_return)
    pd.testing.assert_frame_equal(cdi, original_cdi)
    assert acoes == original_acoes


@pytest.mark.parametrize("limited_component", ["acoes_top20", "fiis_top20", "IVVB11"])
def test_fallback_cdi_nao_estende_componentes_sem_cobertura(limited_component):
    dates = ["2026-10-12", "2026-10-19", "2026-10-26"]
    rows = [{"data": date, "valor": value} for date, value in zip(dates, [100, 110, 120])]
    acoes = rows[:-1] if limited_component == "acoes_top20" else rows
    fiis = rows[:-1] if limited_component == "fiis_top20" else rows
    ivvb = rows[:-1] if limited_component == "IVVB11" else rows
    result = _build_hybrid_portfolio(
        acoes_series=acoes, fiis_series=fiis,
        benchmarks={
            "CDI": pd.DataFrame({"data": pd.to_datetime([dates[0], "2026-10-23"]), "valor": [100, 101]}),
            "IVVB11": pd.DataFrame(ivvb),
        },
        top_acoes=pd.DataFrame(), top_fiis=pd.DataFrame(),
    )
    assert result["disponivel"] is True
    assert result["fim"] == "2026-10-19"
    assert all(row["data"] <= "2026-10-19" for row in result["serie"])


@pytest.mark.parametrize("cdi", [pd.DataFrame(), _benchmark(100, 101).iloc[:1]])
def test_fallback_nao_substitui_historico_cdi_insuficiente(cdi):
    result = _build_hybrid_portfolio(
        acoes_series=_records(100, 110), fiis_series=_records(100, 104),
        benchmarks={"CDI": cdi, "IVVB11": _benchmark(100, 120)},
        top_acoes=pd.DataFrame(), top_fiis=pd.DataFrame(),
    )
    assert result["disponivel"] is False
    assert "CDI" in result["motivo"]
    assert result["serie"] == []

import json

import pandas as pd
import pytest

from src.backtest_engine import run_portfolio_backtest


def _portfolio() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Data_Carteira": ["2026-01-02", "2026-01-02", "2026-01-06", "2026-01-06"],
            "Tipo": ["FII"] * 4,
            "Ticker": ["AAAA11", "BBBB11", "AAAA11", "CCCC11"],
            "Tipo_Completo": [True] * 4,
        }
    )


def _prices() -> pd.DataFrame:
    rows = []
    values = {
        "AAAA11": [10, 11, 12, 13],
        "BBBB11": [20, 22, 24, 26],
        "CCCC11": [30, 30, 33, 36],
        "XFIX11": [100, 101, 102, 103],
    }
    for ticker, prices in values.items():
        for date, price in zip(pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-07", "2026-01-08"]), prices):
            rows.append({"Data": date, "Ticker": ticker, "Adjusted_Close": price})
    return pd.DataFrame(rows)


def test_backtest_entra_no_pregao_seguinte_e_aplica_custo():
    periods, curve, summary = run_portfolio_backtest(
        _portfolio(),
        _prices(),
        tipo="FII",
        end_date="2026-01-08",
        transaction_cost_bps=10,
        benchmark_tickers={"IFIX_PROXY": "XFIX11"},
    )

    assert periods.iloc[0]["Data_Entrada"] == "2026-01-05"
    assert periods.iloc[0]["Data_Saida"] == "2026-01-07"
    assert periods.iloc[0]["Retorno_Bruto"] == pytest.approx((12 / 11 - 1 + 24 / 22 - 1) / 2)
    assert periods.iloc[0]["Custo_Bps"] == pytest.approx(10.0)
    assert periods.iloc[1]["Turnover"] == pytest.approx(0.5)
    assert curve.iloc[-1]["Base100"] == pytest.approx(periods.iloc[-1]["Base100"])
    assert summary["periodos"] == 2


def test_ativo_sem_preco_vira_caixa_e_fica_auditavel():
    prices = _prices()
    prices = prices[prices["Ticker"].ne("BBBB11")]

    periods, _, summary = run_portfolio_backtest(
        _portfolio(), prices, tipo="FII", end_date="2026-01-08", transaction_cost_bps=0
    )

    first = periods.iloc[0]
    assert first["Ativos"] == 2
    assert first["Ativos_Com_Preco"] == 1
    assert first["Cobertura_Pct"] == 50.0
    assert json.loads(first["Tickers_Sem_Preco"]) == ["BBBB11"]
    assert summary["cobertura_media_pct"] == 75.0


def test_politica_error_interrompe_quando_preco_ausente():
    prices = _prices()
    prices = prices[prices["Ticker"].ne("BBBB11")]
    with pytest.raises(ValueError, match="BBBB11"):
        run_portfolio_backtest(
            _portfolio(),
            prices,
            tipo="FII",
            end_date="2026-01-08",
            missing_asset_policy="error",
        )

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.backtest import (
    _chain_base100,
    _resolve_date_col,
    load_top20_snapshots,
    run_backtest,
)


def test_resolve_date_col():
    df = pd.DataFrame(columns=["Data Preco", "FUNDOS"])
    assert _resolve_date_col(df) == "Data Preco"

    df2 = pd.DataFrame(columns=["Data Preço", "FUNDOS"])
    assert _resolve_date_col(df2) == "Data Preço"


def test_load_top20_snapshots(tmp_path):
    path = tmp_path / "top20.xlsx"
    df = pd.DataFrame({
        "FUNDOS": ["HGLG11", "XPLG11", "HGLG11", "KNRI11"],
        "Data Preco": ["2026-06-18", "2026-06-18", "2026-06-23", "2026-06-23"],
    })
    df.to_excel(path, index=False)

    snapshots = load_top20_snapshots(str(path))
    assert len(snapshots) == 2
    assert snapshots[0][1] == ["HGLG11", "XPLG11"]
    assert snapshots[1][1] == ["HGLG11", "KNRI11"]


def test_chain_base100():
    assert _chain_base100(100.0, 0.05) == pytest.approx(105.0)
    assert _chain_base100(105.0, None) == pytest.approx(105.0)


def test_run_backtest_sem_historico(tmp_path):
    result = run_backtest(str(tmp_path / "inexistente.xlsx"))
    assert result["disponivel"] is False


def test_run_backtest_com_mock(monkeypatch, tmp_path):
    path = tmp_path / "top20.xlsx"
    pd.DataFrame({
        "FUNDOS": ["AAA11", "BBB11"],
        "Data Preco": ["2026-06-01", "2026-06-01"],
    }).to_excel(path, index=False)

    def fake_portfolio(tickers, start, end):
        return 0.10

    def fake_asset(ticker, start, end):
        if ticker == "XFIX11.SA":
            return 0.05
        if ticker == "^BVSP":
            return 0.03
        return 0.02

    monkeypatch.setattr("src.backtest._portfolio_return", fake_portfolio)
    monkeypatch.setattr("src.backtest._asset_return", fake_asset)

    result = run_backtest(str(path), data_fim="2026-06-10")
    assert result["disponivel"] is True
    assert result["bateu_ifix"] is True
    assert result["bateu_ibov"] is True
    assert result["carteira_top20_fiis"]["base100"] == pytest.approx(110.0)

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
    save_portfolio_snapshot,
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


def _top_fiis_fake():
    return pd.DataFrame({
        "FUNDOS": ["AAA11", "BBB11"],
        "PREÇO ATUAL (R$)": [10.0, 20.0],
        "Score": [80.0, 70.0],
    })


def _top_acoes_fake():
    # O Investsite entrega a coluna acentuada. Já houve regressão por ler "Acao".
    return pd.DataFrame({
        "Ação": ["ABCD3", "EFGH4"],
        "Preço": [5.0, 6.0],
        "Score": [60.0, 50.0],
    })


def test_save_portfolio_snapshot_registra_fiis_e_acoes(tmp_path):
    out = tmp_path / "carteiras.parquet"

    save_portfolio_snapshot(
        top_fiis=_top_fiis_fake(),
        top_acoes=_top_acoes_fake(),
        data_execucao="2026-08-20",
        output_file=str(out),
    )

    df = pd.read_parquet(out)

    assert sorted(df["Tipo"].unique()) == ["ACAO", "FII"]
    assert df["Tipo"].value_counts().to_dict() == {"FII": 2, "ACAO": 2}
    assert set(df["Ticker"]) == {"AAA11", "BBB11", "ABCD3", "EFGH4"}


def test_save_portfolio_snapshot_preserva_preco_score_posicao(tmp_path):
    """Sem Preco_Entrada a carteira não serve para backtest."""
    out = tmp_path / "carteiras.parquet"

    save_portfolio_snapshot(
        top_fiis=_top_fiis_fake(),
        top_acoes=_top_acoes_fake(),
        data_execucao="2026-08-20",
        output_file=str(out),
    )

    df = pd.read_parquet(out)

    assert df[["Data_Carteira", "Tipo", "Preco_Entrada", "Score", "Posicao"]].notna().all().all()

    acao = df[df["Ticker"] == "ABCD3"].iloc[0]
    assert acao["Preco_Entrada"] == pytest.approx(5.0)
    assert acao["Score"] == pytest.approx(60.0)
    assert acao["Posicao"] == 1

    # Posição é reiniciada por tipo.
    assert sorted(df[df["Tipo"] == "FII"]["Posicao"]) == [1, 2]
    assert sorted(df[df["Tipo"] == "ACAO"]["Posicao"]) == [1, 2]


def test_save_portfolio_snapshot_aceita_acao_sem_acento(tmp_path):
    out = tmp_path / "carteiras.parquet"

    save_portfolio_snapshot(
        top_fiis=pd.DataFrame(),
        top_acoes=pd.DataFrame({"Acao": ["ABCD3"], "Preço": [5.0], "Score": [60.0]}),
        data_execucao="2026-08-20",
        output_file=str(out),
    )

    df = pd.read_parquet(out)
    assert df["Ticker"].tolist() == ["ABCD3"]


def test_save_portfolio_snapshot_substitui_carteira_do_mesmo_dia(tmp_path):
    out = tmp_path / "carteiras.parquet"

    save_portfolio_snapshot(
        top_fiis=_top_fiis_fake(),
        top_acoes=_top_acoes_fake(),
        data_execucao="2026-08-20",
        output_file=str(out),
    )

    # Segunda execução do mesmo dia com seleção diferente.
    save_portfolio_snapshot(
        top_fiis=pd.DataFrame({"FUNDOS": ["CCC11"], "PREÇO ATUAL (R$)": [30.0], "Score": [90.0]}),
        top_acoes=pd.DataFrame(),
        data_execucao="2026-08-20",
        output_file=str(out),
    )

    df = pd.read_parquet(out)
    assert df["Ticker"].tolist() == ["CCC11"]

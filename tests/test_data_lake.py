from pathlib import Path
import json

import pandas as pd

from src.data_lake import (
    _portfolio_from_top,
    list_lake_dates,
    read_lake_dataset,
    rebuild_dashboard_index,
    rebuild_legacy_tables_from_lake,
    run_data_quality_checks,
    save_lake_snapshot,
)


def test_data_lake_snapshot_and_rebuild(tmp_path: Path):
    data_dir = tmp_path / "data"
    dashboard_dir = tmp_path / "docs" / "data"
    dashboard_dir.mkdir(parents=True)
    (dashboard_dir / "2026-06-29.json").write_text("{}", encoding="utf-8")

    fii_universe = pd.DataFrame({"FUNDOS": ["AAA11"], "PREÇO ATUAL (R$)": [10.0], "Score": [55.0]})
    acoes_universe = pd.DataFrame({"Ação": ["ABCD3"], "Preço": [20.0], "Score": [60.0]})
    top_fiis = fii_universe.copy()
    top_acoes = acoes_universe.copy()

    save_lake_snapshot(
        data_dir=data_dir,
        data_execucao="2026-06-29",
        fii_universe=fii_universe,
        acoes_universe=acoes_universe,
        top_fiis=top_fiis,
        top_acoes=top_acoes,
    )

    assert list_lake_dates(data_dir) == ["2026-06-29"]
    assert not read_lake_dataset(data_dir, "fii_universe.parquet").empty

    rebuilt = rebuild_legacy_tables_from_lake(data_dir)
    assert rebuilt["historico_fiis_rows"] == 1
    assert rebuilt["historico_acoes_rows"] == 1
    assert rebuilt["carteiras_rows"] == 2

    index_dates = rebuild_dashboard_index(dashboard_dir)
    assert index_dates == ["2026-06-29"]

    report = run_data_quality_checks(data_dir=data_dir, dashboard_dir=dashboard_dir)
    assert report["status"] in {"ok", "warn"}


def test_portfolio_from_top_preenche_data_e_tipo():
    """Regressão: escalares atribuídos a um DataFrame vazio viravam NaN."""
    top = pd.DataFrame({
        "FUNDOS": ["AAA11", "BBB11", "CCC11"],
        "PREÇO ATUAL (R$)": [10.0, 20.0, 30.0],
        "Score": [80.0, 70.0, 60.0],
    })

    out = _portfolio_from_top(top, "FII", "2026-08-20")

    assert len(out) == 3
    assert out["Data_Carteira"].tolist() == ["2026-08-20"] * 3
    assert out["Tipo"].tolist() == ["FII"] * 3
    assert out["Posicao"].tolist() == [1, 2, 3]
    assert out[["Data_Carteira", "Tipo", "Preco_Entrada", "Score"]].notna().all().all()


def test_portfolio_from_top_ignora_indice_nao_sequencial():
    """Um Top N filtrado chega com índice esburacado; isso não pode gerar NaN."""
    top = pd.DataFrame(
        {"Ação": ["ABCD3", "EFGH4"], "Preço": [5.0, 6.0], "Score": [60.0, 50.0]},
        index=[7, 19],
    )

    out = _portfolio_from_top(top, "ACAO", "2026-08-20")

    assert out["Ticker"].tolist() == ["ABCD3", "EFGH4"]
    assert out.notna().all().all()


def _snapshot_com_top(data_dir: Path, date_str: str):
    save_lake_snapshot(
        data_dir=data_dir,
        data_execucao=date_str,
        fii_universe=pd.DataFrame({"FUNDOS": ["AAA11"], "PREÇO ATUAL (R$)": [10.0], "Score": [55.0]}),
        acoes_universe=pd.DataFrame({"Ação": ["ABCD3"], "Preço": [20.0], "Score": [60.0]}),
        top_fiis=pd.DataFrame({"FUNDOS": ["AAA11"], "PREÇO ATUAL (R$)": [10.0], "Score": [55.0]}),
        top_acoes=pd.DataFrame({"Ação": ["ABCD3"], "Preço": [20.0], "Score": [60.0]}),
    )


def test_rebuild_carteira_sem_chaves_nulas(tmp_path: Path):
    data_dir = tmp_path / "data"
    _snapshot_com_top(data_dir, "2026-06-29")

    rebuild_legacy_tables_from_lake(data_dir)

    cart = pd.read_parquet(data_dir / "backtest" / "carteiras_historicas.parquet")
    assert len(cart) == 2
    assert cart[["Data_Carteira", "Tipo", "Ticker", "Preco_Entrada", "Score", "Posicao"]].notna().all().all()
    assert sorted(cart["Tipo"]) == ["ACAO", "FII"]


def test_rebuild_prioriza_top_sobre_carteira_residual(tmp_path: Path):
    """carteira.parquet pode carregar resíduo de execução repetida do dia."""
    data_dir = tmp_path / "data"
    _snapshot_com_top(data_dir, "2026-06-29")

    # Simula resíduo: um ativo que não está no Top N daquele dia.
    residuo = pd.DataFrame({
        "Data_Carteira": ["2026-06-29"],
        "Tipo": ["FII"],
        "Ticker": ["ZZZ11"],
        "Preco_Entrada": [99.0],
        "Score": [10.0],
        "Posicao": [1],
    })
    residuo.to_parquet(data_dir / "lake" / "snapshots" / "2026-06-29" / "carteira.parquet", index=False)

    rebuild_legacy_tables_from_lake(data_dir)

    cart = pd.read_parquet(data_dir / "backtest" / "carteiras_historicas.parquet")
    assert "ZZZ11" not in cart["Ticker"].tolist()
    assert sorted(cart["Ticker"]) == ["AAA11", "ABCD3"]


def test_quality_checks_detectam_chave_nula_e_tipo_faltando(tmp_path: Path):
    data_dir = tmp_path / "data"
    _snapshot_com_top(data_dir, "2026-06-29")
    rebuild_legacy_tables_from_lake(data_dir)

    carteira_path = data_dir / "backtest" / "carteiras_historicas.parquet"
    cart = pd.read_parquet(carteira_path)

    # Corrompe do jeito que o bug real corrompia: chave nula + só um tipo.
    cart.loc[cart["Tipo"] == "ACAO", ["Data_Carteira", "Tipo"]] = None
    cart.to_parquet(carteira_path, index=False)

    report = run_data_quality_checks(data_dir=data_dir)
    checks = {c["name"]: c["status"] for c in report["checks"]}

    assert checks["chaves_nulas_carteiras_historicas.parquet"] == "error"
    assert checks["carteira_cobertura_tipos"] == "error"
    assert report["status"] == "error"


def test_quality_checks_detectam_preco_entrada_ausente(tmp_path: Path):
    data_dir = tmp_path / "data"
    _snapshot_com_top(data_dir, "2026-06-29")
    rebuild_legacy_tables_from_lake(data_dir)

    carteira_path = data_dir / "backtest" / "carteiras_historicas.parquet"
    cart = pd.read_parquet(carteira_path)
    cart["Preco_Entrada"] = None
    cart.to_parquet(carteira_path, index=False)

    report = run_data_quality_checks(data_dir=data_dir)
    checks = {c["name"]: c["status"] for c in report["checks"]}

    assert checks["carteira_preco_entrada"] == "error"


def test_quality_checks_sinalizam_snapshot_historico_marcado_como_incompleto(tmp_path: Path):
    data_dir = tmp_path / "data"
    _snapshot_com_top(data_dir, "2026-06-29")
    rebuild_legacy_tables_from_lake(data_dir)

    carteira_path = data_dir / "backtest" / "carteiras_historicas.parquet"
    cart = pd.read_parquet(carteira_path)
    cart = cart[cart["Tipo"] == "FII"].copy()
    cart.to_parquet(carteira_path, index=False)

    marker = data_dir / "lake" / "known_incomplete_snapshots.json"
    marker.write_text(
        json.dumps({"dates": {"2026-06-29": "Ações não foram coletadas."}}),
        encoding="utf-8",
    )

    report = run_data_quality_checks(data_dir=data_dir)
    checks = {check["name"]: check["status"] for check in report["checks"]}

    assert checks["known_incomplete_snapshots"] == "warn"
    assert checks["carteira_cobertura_tipos"] == "warn"
    assert report["status"] == "warn"

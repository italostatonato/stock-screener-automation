import json
from pathlib import Path

import pandas as pd

from src.data_lake import save_lake_snapshot
from src.observed_history import (
    build_observed_history,
    load_dashboard_portfolios,
)


def _write_dashboard(path: Path, date_str: str, fiis: list, acoes: list) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{date_str}.json").write_text(
        json.dumps({"data": date_str, "fiis": fiis, "acoes": acoes}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_load_dashboard_tolera_cabecalhos_mojibake(tmp_path: Path):
    docs = tmp_path / "docs"
    _write_dashboard(
        docs,
        "2026-06-21",
        [{"FUNDOS": "HGLG11", "PRE�O ATUAL (R$)": "R$ 150,25", "score": 72.0}],
        [{"A��o": "PETR4", "Pre�o": "31,50", "score": 68.0}],
    )

    out = load_dashboard_portfolios(docs)

    assert sorted(out["Ticker"]) == ["HGLG11", "PETR4"]
    assert out.set_index("Ticker").loc["HGLG11", "Preco_Entrada"] == 150.25
    assert out.set_index("Ticker").loc["PETR4", "Preco_Entrada"] == 31.5


def test_build_observed_prioriza_lake_e_marca_data_incompleta(tmp_path: Path):
    data_dir = tmp_path / "data"
    docs = tmp_path / "docs"
    _write_dashboard(
        docs,
        "2026-06-29",
        [{"FUNDOS": f"AAAA{i:02d}", "PREÇO ATUAL (R$)": 10 + i} for i in range(20)],
        [{"Ação": f"BBBB{i:02d}", "Preço": 20 + i} for i in range(20)],
    )
    _write_dashboard(
        docs,
        "2026-06-30",
        [{"FUNDOS": f"CCCC{i:02d}", "PREÇO ATUAL (R$)": 10 + i} for i in range(15)],
        [],
    )

    lake_fiis = pd.DataFrame(
        {"FUNDOS": [f"AAAA{i:02d}" for i in range(20)], "PREÇO ATUAL (R$)": [99.0] * 20}
    )
    lake_acoes = pd.DataFrame(
        {"Ação": [f"BBBB{i:02d}" for i in range(20)], "Preço": [88.0] * 20}
    )
    save_lake_snapshot(
        data_dir=data_dir,
        data_execucao="2026-06-29",
        fii_universe=lake_fiis,
        acoes_universe=lake_acoes,
        top_fiis=lake_fiis,
        top_acoes=lake_acoes,
    )

    out, manifest = build_observed_history(data_dir=data_dir, docs_data_dir=docs)

    assert out.loc[out["Data_Carteira"].eq("2026-06-29"), "Origem"].eq("lake_top").all()
    assert out.loc[out["Data_Carteira"].eq("2026-06-29"), "Preco_Entrada"].isin([88.0, 99.0]).all()
    assert len(out.loc[out["Data_Carteira"].eq("2026-06-29")]) == 40
    assert manifest["total_datas"] == 2
    assert manifest["datas_completas"] == 1
    assert manifest["datas_incompletas"] == ["2026-06-30"]
    assert (data_dir / "backtest" / "observed_portfolios.parquet").exists()

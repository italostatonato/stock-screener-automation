from pathlib import Path

import pandas as pd

from src.data_lake import (
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

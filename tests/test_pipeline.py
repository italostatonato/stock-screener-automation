from unittest.mock import Mock

import pandas as pd
import pytest

import main as pipeline


@pytest.fixture
def stages(monkeypatch, tmp_path):
    cfg = {
        "paths": {name: str(tmp_path / name) for name in (
            "data_dir", "old_dir", "output_dir", "logs_dir", "local_input_file"
        )},
        "scraper": {}, "columns": {},
    }
    fiis = pd.DataFrame({"FUNDOS": ["TEST11"], "Score": [70.0]})
    acoes = pd.DataFrame({"Ação": ["TEST3"], "Score": [80.0]})
    values = {
        "load_config": cfg, "scrape_fundsexplorer": fiis,
        "clean_and_normalize": fiis, "score_fiis": fiis.Score,
        "select_top_fiis": (fiis.copy(), fiis.copy()),
        "scrape_acoes": acoes, "score_acoes": acoes.Score,
        "select_top_acoes": (acoes.copy(), acoes.copy()),
        "get_market_indicators": {}, "get_benchmarks": {}, "run_backtest": {},
        "run_data_quality_checks": {"status": "ok"},
    }
    names = list(values) + [
        "setup_logging", "update_history", "append_historical_data",
        "save_portfolio_snapshot", "save_lake_snapshot",
        "rebuild_legacy_tables_from_lake", "build_all_datasets", "run_ml_pipeline",
        "save_snapshot", "format_workbook", "export_dashboard_json", "deliver_excel",
    ]
    mocks = {}
    for name in names:
        mocks[name] = Mock(return_value=values[name]) if name in values else Mock()
        monkeypatch.setattr(pipeline, name, mocks[name])
    return mocks


def test_no_history_written_before_both_rankings_are_valid(stages):
    stages["scrape_acoes"].return_value = pd.DataFrame()
    with pytest.raises(RuntimeError, match="vazio"):
        pipeline.main()
    for name in ("update_history", "append_historical_data", "save_lake_snapshot"):
        stages[name].assert_not_called()


@pytest.mark.parametrize("stage", [
    "save_lake_snapshot", "rebuild_legacy_tables_from_lake",
    "export_dashboard_json", "run_data_quality_checks",
])
def test_critical_failure_stops_pipeline(stages, stage):
    stages[stage].side_effect = OSError("disk unavailable")
    with pytest.raises(RuntimeError):
        pipeline.main()
    stages["deliver_excel"].assert_not_called()


def test_quality_error_stops_delivery(stages):
    stages["run_data_quality_checks"].return_value = {"status": "error"}
    with pytest.raises(RuntimeError, match="qualidade"):
        pipeline.main()
    stages["deliver_excel"].assert_not_called()


def test_dataset_failure_does_not_train_stale_dataset(stages):
    stages["build_all_datasets"].side_effect = ValueError("invalid dataset")
    pipeline.main()
    stages["run_ml_pipeline"].assert_not_called()


def test_operational_pipeline_trains_seven_day_horizon(stages):
    pipeline.main()
    assert stages["run_ml_pipeline"].call_args.kwargs["horizon"] == 7
    assert stages["run_data_quality_checks"].call_args.kwargs["expected_date"] == pipeline.current_run_date()

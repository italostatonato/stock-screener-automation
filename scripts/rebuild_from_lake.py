"""Reconstrói derivados a partir do data lake.

Uso:
  python scripts/rebuild_from_lake.py

O script não roda scraping. Ele usa data/lake/snapshots como fonte oficial e
recria parquets consolidados, datasets ML, previsões dos modelos e relatórios.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_lake import (  # noqa: E402
    rebuild_legacy_tables_from_lake,
    rebuild_dashboard_index,
    run_data_quality_checks,
    update_lake_manifest,
)
from src.dataset_builder import build_all_datasets  # noqa: E402
from src.ml_models import run_ml_pipeline  # noqa: E402


def main() -> int:
    data_dir = PROJECT_ROOT / "data"
    dashboard_dir = PROJECT_ROOT / "docs" / "data"

    rebuild_result = rebuild_legacy_tables_from_lake(data_dir)
    build_all_datasets(data_dir=str(data_dir), horizons=(7, 30, 60, 90))
    run_ml_pipeline(data_dir=str(data_dir), horizon=30)
    update_lake_manifest(data_dir)
    rebuild_dashboard_index(dashboard_dir)
    quality = run_data_quality_checks(data_dir=data_dir, dashboard_dir=dashboard_dir)

    payload = {
        "rebuild": rebuild_result,
        "quality": quality,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if quality.get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())

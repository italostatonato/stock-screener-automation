"""Executa checagens de saúde da camada de dados.

Uso:
  python scripts/healthcheck_data.py
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Permite executar o script a partir da raiz do projeto.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_lake import run_data_quality_checks, update_lake_manifest, rebuild_dashboard_index


def main() -> int:
    data_dir = PROJECT_ROOT / "data"
    dashboard_dir = PROJECT_ROOT / "docs" / "data"

    update_lake_manifest(data_dir)
    rebuild_dashboard_index(dashboard_dir)
    report = run_data_quality_checks(data_dir=data_dir, dashboard_dir=dashboard_dir)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())

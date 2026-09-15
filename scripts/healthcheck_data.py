"""Executa checagens de saúde da camada de dados.

Uso:
  python scripts/healthcheck_data.py
"""

from __future__ import annotations

import json
import argparse
from pathlib import Path
import sys

# Permite executar o script a partir da raiz do projeto.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_lake import run_data_quality_checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", help="Verifica sem alterar manifesto, índice ou relatório.")
    args = parser.parse_args()
    data_dir = PROJECT_ROOT / "data"
    dashboard_dir = PROJECT_ROOT / "docs" / "data"

    report = run_data_quality_checks(data_dir=data_dir, dashboard_dir=dashboard_dir, read_only=args.read_only)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())

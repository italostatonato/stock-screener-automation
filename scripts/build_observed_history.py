"""Reconstrói o histórico das carteiras efetivamente publicadas.

Uso:
  python scripts/build_observed_history.py

Os JSONs versionados do dashboard são a base portátil. Caso ``data/output``
exista localmente, Excels anteriores também são incorporados. O resultado é
mantido separado dos universos completos do lake.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.observed_history import build_observed_history  # noqa: E402


def main() -> int:
    _, manifest = build_observed_history(
        data_dir=PROJECT_ROOT / "data",
        docs_data_dir=PROJECT_ROOT / "docs" / "data",
        excel_dirs=(PROJECT_ROOT / "data" / "output",),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

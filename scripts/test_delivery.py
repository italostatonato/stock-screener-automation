"""Teste manual da entrega do Excel final.

Uso:
    python scripts/test_delivery.py
    python scripts/test_delivery.py --file data/output/Top20_Ranking_2026-07-04.xlsx
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config
from src.delivery import deliver_excel


def find_latest_excel(output_dir: str | Path) -> Path:
    output = Path(output_dir)
    files = sorted(output.glob("Top20_Ranking_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"Nenhum Top20_Ranking_*.xlsx encontrado em {output}")
    return files[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", dest="file", help="Caminho do Excel final para entregar.")
    args = parser.parse_args()

    cfg = load_config(str(PROJECT_ROOT / "config.yaml"))

    excel = Path(args.file) if args.file else find_latest_excel(cfg.get("paths", {}).get("output_dir", "data/output"))
    result = deliver_excel(excel, cfg)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

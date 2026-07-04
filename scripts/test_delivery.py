"""Teste manual da entrega do Excel final.

Uso:
    python scripts/test_delivery.py
    python scripts/test_delivery.py --file data/output/Top20_Ranking_2026-07-04.xlsx
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

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

    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    excel = Path(args.file) if args.file else find_latest_excel(cfg.get("paths", {}).get("output_dir", "data/output"))
    result = deliver_excel(excel, cfg)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

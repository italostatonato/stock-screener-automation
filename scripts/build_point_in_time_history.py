"""Constrói o backfill mensal point-in-time de FIIs com CVM + B3.

Exemplos:
  python scripts/build_point_in_time_history.py --start 2021-01-01
  python scripts/build_point_in_time_history.py --start 2021-01-01 --offline

Os arquivos brutos ficam em ``data/raw`` (ignorado pelo Git). As fundações e
snapshots sintéticos ficam em ``data/point_in_time``, separados do lake real.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config  # noqa: E402
from src.point_in_time import (  # noqa: E402
    B3_COTAHIST_URL,
    CVM_FII_URL,
    build_monthly_fii_backfill,
    download_point_in_time_sources,
    load_b3_cotahist_archives,
    load_cvm_fii_archives,
    source_manifest,
    _atomic_json,
    _atomic_parquet,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    start = pd.Timestamp(args.start).normalize()
    end = pd.Timestamp(args.end).normalize()
    if end < start:
        raise ValueError("--end deve ser igual ou posterior a --start")
    years = list(range(start.year, end.year + 1))
    raw_dir = PROJECT_ROOT / "data" / "raw" / "point_in_time"

    if args.offline:
        archives = {
            "cvm_fii": [raw_dir / "cvm_fii" / f"inf_mensal_fii_{year}.zip" for year in years],
            "b3_cotahist": [raw_dir / "b3" / f"COTAHIST_A{year}.ZIP" for year in years],
        }
        missing = [str(path) for paths in archives.values() for path in paths if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Arquivos brutos ausentes no modo offline: {missing}")
    else:
        archives = download_point_in_time_sources(years, raw_dir=raw_dir)

    print("Lendo Informes Mensais CVM...")
    fundamentals = load_cvm_fii_archives(archives["cvm_fii"])
    print("Lendo COTAHIST B3...")
    prices = load_b3_cotahist_archives(archives["b3_cotahist"])

    foundation = PROJECT_ROOT / "data" / "point_in_time" / "foundation"
    _atomic_parquet(fundamentals, foundation / "cvm_fii_fundamentals.parquet")
    _atomic_parquet(prices, foundation / "b3_cotahist.parquet")
    source_payload = {
        "schema_version": 1,
        "sources": {
            "cvm_fii": {
                "url_template": CVM_FII_URL,
                "files": source_manifest(archives["cvm_fii"], relative_to=PROJECT_ROOT),
            },
            "b3_cotahist": {
                "url_template": B3_COTAHIST_URL,
                "observacao": "preços não ajustados por proventos; usados para features/sinais, não retorno total",
                "files": source_manifest(archives["b3_cotahist"], relative_to=PROJECT_ROOT),
            },
        },
        "fundamental_rows": int(len(fundamentals)),
        "price_rows": int(len(prices)),
    }
    # O manifesto leve fica versionável; os parquets pesados da fundação são cache local.
    _atomic_json(source_payload, PROJECT_ROOT / "data" / "point_in_time" / "source_manifest.json")

    cfg = load_config(str(PROJECT_ROOT / "config.yaml"))
    manifest = build_monthly_fii_backfill(
        fundamentals=fundamentals,
        prices=prices,
        cfg=cfg,
        start=start,
        end=end,
        output_dir=PROJECT_ROOT / "data" / "point_in_time",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["snapshots_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

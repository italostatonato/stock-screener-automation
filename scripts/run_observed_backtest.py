"""Executa o backtest auditável das carteiras efetivamente publicadas.

Uso normal (atualiza preços do Yahoo):
  python scripts/run_observed_backtest.py

Uso sem rede, aproveitando o cache existente:
  python scripts/run_observed_backtest.py --offline
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest_engine import (  # noqa: E402
    download_yahoo_adjusted_prices,
    merge_price_cache,
    run_portfolio_backtest,
)
from src.observed_history import build_observed_history  # noqa: E402


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    frame.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def _atomic_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="não atualiza preços pela rede")
    parser.add_argument("--end-date", default=None, help="data final YYYY-MM-DD")
    parser.add_argument("--transaction-cost-bps", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    data_dir = PROJECT_ROOT / "data"
    backtest_dir = data_dir / "backtest"
    portfolios, observed_manifest = build_observed_history(
        data_dir=data_dir,
        docs_data_dir=PROJECT_ROOT / "docs" / "data",
        excel_dirs=(data_dir / "output",),
    )

    cache_path = backtest_dir / "adjusted_prices.parquet"
    cached = pd.read_parquet(cache_path) if cache_path.exists() else pd.DataFrame()
    end_date = pd.Timestamp(args.end_date).normalize() if args.end_date else pd.Timestamp.today().normalize()
    start_date = pd.to_datetime(portfolios["Data_Carteira"]).min() - pd.Timedelta(3, unit="D")

    if not args.offline:
        portfolio_tickers = portfolios["Ticker"].dropna().astype(str).unique().tolist()
        requested = portfolio_tickers + ["XFIX11", "^BVSP"]
        downloaded = download_yahoo_adjusted_prices(requested, start=start_date, end=end_date)
        cached = merge_price_cache(cached, downloaded)
        _atomic_parquet(cached, cache_path)
    if cached.empty:
        raise RuntimeError(
            "Cache de preços vazio. Rode sem --offline ao menos uma vez para baixar preços ajustados."
        )

    all_periods = []
    summaries = {}
    settings = {
        "FII": {"IFIX_PROXY": "XFIX11"},
        "ACAO": {"IBOV": "^BVSP"},
    }
    for tipo, benchmarks in settings.items():
        periods, curve, summary = run_portfolio_backtest(
            portfolios=portfolios,
            prices=cached,
            tipo=tipo,
            end_date=end_date,
            transaction_cost_bps=args.transaction_cost_bps,
            benchmark_tickers=benchmarks,
        )
        all_periods.append(periods)
        summaries[tipo] = summary
        _atomic_parquet(curve, backtest_dir / f"observed_curve_{tipo.lower()}.parquet")

    period_frame = pd.concat(all_periods, ignore_index=True, sort=False)
    _atomic_parquet(period_frame, backtest_dir / "observed_backtest_periods.parquet")
    payload = {
        "schema_version": 1,
        "natureza": "OBSERVADO",
        "historico": {
            "primeira_data": observed_manifest["primeira_data"],
            "ultima_data": observed_manifest["ultima_data"],
            "total_datas": observed_manifest["total_datas"],
        },
        "backtests": summaries,
    }
    _atomic_json(payload, backtest_dir / "observed_backtest_summary.json")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

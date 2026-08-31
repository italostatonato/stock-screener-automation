"""Executa o backtest mensal dos rankings sintéticos point-in-time de FIIs.

Por padrão, exclui carteiras com menos de ``top_n`` ativos. Ativos sem preço
ajustado permanecem como caixa e são listados na auditoria de cada período.
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
from src.point_in_time import load_fii_backfill_portfolios  # noqa: E402


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
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--transaction-cost-bps", type=float, default=10.0)
    parser.add_argument(
        "--include-partial",
        action="store_true",
        help="inclui datas em que a estratégia legada produziu menos de 20 ativos",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    point_dir = PROJECT_ROOT / "data" / "point_in_time"
    backtest_dir = point_dir / "backtest"
    portfolios = load_fii_backfill_portfolios(point_dir)
    if portfolios.empty:
        raise RuntimeError("Nenhum snapshot point-in-time encontrado; construa o histórico primeiro.")

    cache_path = PROJECT_ROOT / "data" / "backtest" / "adjusted_prices.parquet"
    cached = pd.read_parquet(cache_path) if cache_path.exists() else pd.DataFrame()
    end_date = pd.Timestamp(args.end_date).normalize() if args.end_date else pd.Timestamp.today().normalize()
    start_date = pd.to_datetime(portfolios["Data_Carteira"]).min() - pd.Timedelta(3, unit="D")
    if not args.offline:
        requested = portfolios["Ticker"].dropna().astype(str).unique().tolist() + ["XFIX11"]
        downloaded = download_yahoo_adjusted_prices(requested, start=start_date, end=end_date)
        cached = merge_price_cache(cached, downloaded)
        _atomic_parquet(cached, cache_path)
    if cached.empty:
        raise RuntimeError("Cache de preços vazio; rode uma vez sem --offline.")

    periods, curve, summary = run_portfolio_backtest(
        portfolios=portfolios,
        prices=cached,
        tipo="FII",
        end_date=end_date,
        transaction_cost_bps=args.transaction_cost_bps,
        benchmark_tickers={"IFIX_PROXY": "XFIX11"},
        require_complete_type=not args.include_partial,
    )
    _atomic_parquet(periods, backtest_dir / "fii_periods.parquet")
    _atomic_parquet(curve, backtest_dir / "fii_curve.parquet")

    # Diagnóstico independente do Yahoo: amplia cobertura, mas é somente retorno
    # de preço. O nome e a metodologia deixam explícito que não inclui proventos.
    b3_summary = None
    b3_foundation = point_dir / "foundation" / "b3_cotahist.parquet"
    if b3_foundation.exists():
        b3_prices = pd.read_parquet(
            b3_foundation,
            columns=["Data", "Ticker", "PREÇO ATUAL (R$)", "Fonte_Preco"],
        ).rename(
            columns={"PREÇO ATUAL (R$)": "Adjusted_Close", "Fonte_Preco": "Fonte"}
        )
        b3_periods, b3_curve, b3_summary = run_portfolio_backtest(
            portfolios=portfolios,
            prices=b3_prices,
            tipo="FII",
            end_date=end_date,
            transaction_cost_bps=args.transaction_cost_bps,
            benchmark_tickers={"IFIX_PROXY_PRECO": "XFIX11"},
            require_complete_type=not args.include_partial,
        )
        b3_summary["metodologia"] = (
            "equal_weight; sinal no fechamento D; entrada no próximo pregão; "
            "COTAHIST B3 sem ajuste por proventos (retorno de preço)"
        )
        _atomic_parquet(b3_periods, backtest_dir / "fii_b3_price_only_periods.parquet")
        _atomic_parquet(b3_curve, backtest_dir / "fii_b3_price_only_curve.parquet")

    payload = {
        "schema_version": 2,
        "natureza": "SIMULADO_POINT_IN_TIME",
        "strategy_version": "fii_v1_legacy_selection",
        "carteiras_parciais_incluidas": bool(args.include_partial),
        "summary": summary,
        "b3_price_only_summary": b3_summary,
    }
    _atomic_json(payload, backtest_dir / "fii_summary.json")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

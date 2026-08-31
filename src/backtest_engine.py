"""Motor auditável de backtest para carteiras observadas ou sintéticas.

Regras centrais:
- o sinal é produzido no fechamento de D e só entra no próximo pregão;
- preços devem ser ajustados por proventos/desdobramentos;
- ativos sem preço não somem da média: viram caixa ou causam erro explícito;
- custos incidem sobre o turnover de cada rebalanceamento;
- cada período preserva cobertura, ausências e preços defasados para auditoria.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PRICE_COLUMNS = ["Data", "Ticker", "Adjusted_Close", "Fonte"]


def _normalize_ticker(value: object) -> str:
    ticker = str(value).strip().upper()
    return ticker[:-3] if ticker.endswith(".SA") else ticker


def prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "date": "Data",
        "data": "Data",
        "ticker": "Ticker",
        "symbol": "Ticker",
        "adjusted_close": "Adjusted_Close",
        "adjustedclose": "Adjusted_Close",
        "close": "Adjusted_Close",
        "fonte": "Fonte",
        "source": "Fonte",
    }
    renamed = {
        column: aliases.get(str(column).strip().lower(), column)
        for column in prices.columns
    }
    out = prices.rename(columns=renamed).copy()
    required = {"Data", "Ticker", "Adjusted_Close"}
    missing = required - set(out.columns)
    if missing:
        raise ValueError(f"Preços sem colunas obrigatórias: {sorted(missing)}")
    if "Fonte" not in out.columns:
        out["Fonte"] = "desconhecida"
    out["Data"] = pd.to_datetime(out["Data"], errors="coerce").dt.normalize()
    out["Ticker"] = out["Ticker"].map(_normalize_ticker)
    out["Adjusted_Close"] = pd.to_numeric(out["Adjusted_Close"], errors="coerce")
    out = out.dropna(subset=["Data", "Ticker", "Adjusted_Close"])
    out = out[out["Adjusted_Close"] > 0]
    return (
        out.sort_values(["Data", "Ticker"])
        .drop_duplicates(["Data", "Ticker"], keep="last")
        .reset_index(drop=True)
    )


def _next_trading_date(trading_dates: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    candidates = trading_dates[trading_dates > signal_date]
    return pd.Timestamp(candidates[0]) if len(candidates) else None


def _last_trading_date(
    trading_dates: pd.DatetimeIndex,
    requested_end: pd.Timestamp,
) -> pd.Timestamp | None:
    candidates = trading_dates[trading_dates <= requested_end]
    return pd.Timestamp(candidates[-1]) if len(candidates) else None


def _turnover(previous: set[str], current: set[str]) -> float:
    if not current:
        return 0.0
    if not previous:
        return 1.0
    union = previous | current
    old_weight = 1.0 / len(previous)
    new_weight = 1.0 / len(current)
    return 0.5 * sum(
        abs((new_weight if ticker in current else 0.0) - (old_weight if ticker in previous else 0.0))
        for ticker in union
    )


def _asset_period_return(
    price_matrix: pd.DataFrame,
    ticker: str,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
) -> tuple[float | None, int | None]:
    if ticker not in price_matrix.columns:
        return None, None
    entry = price_matrix.at[entry_date, ticker] if entry_date in price_matrix.index else np.nan
    if pd.isna(entry) or float(entry) <= 0:
        return None, None
    history = price_matrix.loc[
        (price_matrix.index >= entry_date) & (price_matrix.index <= exit_date), ticker
    ].dropna()
    if history.empty:
        return None, None
    last_date = pd.Timestamp(history.index[-1])
    last_price = float(history.iloc[-1])
    stale_days = int((exit_date - last_date).days)
    return (last_price / float(entry)) - 1.0, stale_days


def _benchmark_return(
    price_matrix: pd.DataFrame,
    ticker: str,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
) -> float | None:
    value, _ = _asset_period_return(price_matrix, _normalize_ticker(ticker), entry_date, exit_date)
    return value


def run_portfolio_backtest(
    portfolios: pd.DataFrame,
    prices: pd.DataFrame,
    tipo: str,
    end_date: str | pd.Timestamp | None = None,
    transaction_cost_bps: float = 10.0,
    missing_asset_policy: str = "cash",
    benchmark_tickers: Mapping[str, str] | None = None,
    require_complete_type: bool = True,
    max_stale_days: int = 7,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Executa backtest equal-weight e devolve períodos, curva e resumo."""
    if missing_asset_policy not in {"cash", "error"}:
        raise ValueError("missing_asset_policy deve ser 'cash' ou 'error'.")
    required = {"Data_Carteira", "Tipo", "Ticker"}
    missing = required - set(portfolios.columns)
    if missing:
        raise ValueError(f"Carteiras sem colunas obrigatórias: {sorted(missing)}")

    p = portfolios.copy()
    p["Data_Carteira"] = pd.to_datetime(p["Data_Carteira"], errors="coerce").dt.normalize()
    p["Tipo"] = p["Tipo"].astype(str).str.strip().str.upper()
    p["Ticker"] = p["Ticker"].map(_normalize_ticker)
    p = p[p["Tipo"].eq(tipo.strip().upper())].dropna(subset=["Data_Carteira", "Ticker"])
    if require_complete_type and "Tipo_Completo" in p.columns:
        p = p[p["Tipo_Completo"].fillna(False).astype(bool)]
    p = p.drop_duplicates(["Data_Carteira", "Ticker"], keep="last")
    if p.empty:
        raise ValueError(f"Nenhuma carteira válida para {tipo}.")

    normalized_prices = prepare_prices(prices)
    if normalized_prices.empty:
        raise ValueError("Série de preços vazia.")
    price_matrix = normalized_prices.pivot(index="Data", columns="Ticker", values="Adjusted_Close").sort_index()
    trading_dates = pd.DatetimeIndex(price_matrix.index.unique()).sort_values()
    signals = sorted(pd.Timestamp(value) for value in p["Data_Carteira"].unique())
    requested_end = pd.Timestamp(end_date).normalize() if end_date is not None else trading_dates[-1]

    periods: list[dict] = []
    previous_tickers: set[str] = set()
    base100 = 100.0
    benchmark_base = {name: 100.0 for name in (benchmark_tickers or {})}

    for index, signal_date in enumerate(signals):
        entry_date = _next_trading_date(trading_dates, signal_date)
        if entry_date is None or entry_date > requested_end:
            continue
        if index + 1 < len(signals):
            exit_date = _next_trading_date(trading_dates, signals[index + 1])
            if exit_date is None:
                exit_date = _last_trading_date(trading_dates, requested_end)
            elif exit_date > requested_end:
                exit_date = _last_trading_date(trading_dates, requested_end)
        else:
            exit_date = _last_trading_date(trading_dates, requested_end)
        if exit_date is None or exit_date <= entry_date:
            continue

        tickers = set(
            p.loc[p["Data_Carteira"].eq(signal_date), "Ticker"]
            .dropna()
            .astype(str)
            .tolist()
        )
        if not tickers:
            continue

        returns: list[float] = []
        missing_tickers: list[str] = []
        stale_tickers: dict[str, int] = {}
        for ticker in sorted(tickers):
            asset_return, stale_days = _asset_period_return(
                price_matrix, ticker, entry_date, exit_date
            )
            if asset_return is None:
                missing_tickers.append(ticker)
                if missing_asset_policy == "error":
                    raise ValueError(
                        f"Sem preço para {ticker} em {entry_date.date()} -> {exit_date.date()}"
                    )
                returns.append(0.0)
                continue
            returns.append(float(asset_return))
            if stale_days is not None and stale_days > max_stale_days:
                stale_tickers[ticker] = stale_days

        gross_return = float(np.mean(returns))
        turnover = _turnover(previous_tickers, tickers)
        cost_fraction = max(float(transaction_cost_bps), 0.0) / 10_000.0 * turnover
        net_return = (1.0 + gross_return) * (1.0 - cost_fraction) - 1.0
        base100 *= 1.0 + net_return

        row = {
            "Tipo": tipo.strip().upper(),
            "Data_Sinal": signal_date.strftime("%Y-%m-%d"),
            "Data_Entrada": entry_date.strftime("%Y-%m-%d"),
            "Data_Saida": exit_date.strftime("%Y-%m-%d"),
            "Ativos": len(tickers),
            "Ativos_Com_Preco": len(tickers) - len(missing_tickers),
            "Cobertura_Pct": round((len(tickers) - len(missing_tickers)) / len(tickers) * 100, 4),
            "Tickers_Sem_Preco": json.dumps(missing_tickers, ensure_ascii=False),
            "Tickers_Defasados": json.dumps(stale_tickers, ensure_ascii=False, sort_keys=True),
            "Turnover": turnover,
            "Custo_Bps": float(transaction_cost_bps) * turnover,
            "Retorno_Bruto": gross_return,
            "Retorno_Liquido": net_return,
            "Base100": base100,
        }
        for name, ticker in (benchmark_tickers or {}).items():
            benchmark_return = _benchmark_return(price_matrix, ticker, entry_date, exit_date)
            row[f"Retorno_{name}"] = benchmark_return
            if benchmark_return is not None:
                benchmark_base[name] *= 1.0 + benchmark_return
            row[f"Base100_{name}"] = benchmark_base[name]
        periods.append(row)
        previous_tickers = tickers

    period_df = pd.DataFrame(periods)
    if period_df.empty:
        raise ValueError("Nenhum período pôde ser calculado com os preços fornecidos.")
    curve_columns = ["Data_Saida", "Base100"] + [
        column for column in period_df.columns if column.startswith("Base100_")
    ]
    curve = period_df[curve_columns].rename(columns={"Data_Saida": "Data"}).copy()
    first_entry = pd.Timestamp(period_df.iloc[0]["Data_Entrada"])
    last_exit = pd.Timestamp(period_df.iloc[-1]["Data_Saida"])
    elapsed_days = max(int((last_exit - first_entry).days), 1)
    total_return = float(period_df.iloc[-1]["Base100"] / 100.0 - 1.0)
    cagr = (1.0 + total_return) ** (365.25 / elapsed_days) - 1.0 if total_return > -1 else -1.0
    running_peak = period_df["Base100"].cummax()
    drawdown = period_df["Base100"] / running_peak - 1.0
    summary = {
        "tipo": tipo.strip().upper(),
        "metodologia": "equal_weight; sinal no fechamento D; entrada no próximo pregão; preços ajustados",
        "primeiro_sinal": period_df.iloc[0]["Data_Sinal"],
        "primeira_entrada": period_df.iloc[0]["Data_Entrada"],
        "ultima_saida": period_df.iloc[-1]["Data_Saida"],
        "periodos": int(len(period_df)),
        "retorno_liquido_pct": round(total_return * 100, 4),
        "cagr_pct": round(cagr * 100, 4),
        "max_drawdown_pct": round(float(drawdown.min()) * 100, 4),
        "cobertura_media_pct": round(float(period_df["Cobertura_Pct"].mean()), 4),
        "turnover_medio_pct": round(float(period_df["Turnover"].mean()) * 100, 4),
        "custo_configurado_bps": float(transaction_cost_bps),
        "missing_asset_policy": missing_asset_policy,
        "precos_defasados_periodos": int(period_df["Tickers_Defasados"].ne("{}").sum()),
    }
    for name in (benchmark_tickers or {}):
        value = float(period_df.iloc[-1][f"Base100_{name}"] / 100.0 - 1.0)
        summary[f"retorno_{name.lower()}_pct"] = round(value * 100, 4)
        summary[f"alpha_vs_{name.lower()}_pct"] = round((total_return - value) * 100, 4)
    return period_df, curve, summary


def _yahoo_symbol(ticker: str) -> str:
    normalized = str(ticker).strip().upper()
    if normalized.startswith("^") or normalized.endswith(".SA") or "=" in normalized:
        return normalized
    return f"{normalized}.SA"


def download_yahoo_adjusted_prices(
    tickers: Iterable[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    batch_size: int = 40,
) -> pd.DataFrame:
    """Baixa fechamentos ajustados do Yahoo em lotes e formato longo."""
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependência do ambiente
        raise RuntimeError("yfinance não está instalado.") from exc

    symbols = sorted({_yahoo_symbol(ticker) for ticker in tickers if str(ticker).strip()})
    start_ts = pd.Timestamp(start).normalize()
    # O parâmetro end do Yahoo é exclusivo.
    end_exclusive = pd.Timestamp(end).normalize() + pd.Timedelta(days=1)
    frames: list[pd.DataFrame] = []
    for offset in range(0, len(symbols), max(int(batch_size), 1)):
        batch = symbols[offset : offset + max(int(batch_size), 1)]
        raw = yf.download(
            batch,
            start=start_ts.strftime("%Y-%m-%d"),
            end=end_exclusive.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        if raw.empty:
            logger.warning("Yahoo sem dados para lote de %d símbolos", len(batch))
            continue
        for symbol in batch:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    if symbol in raw.columns.get_level_values(0):
                        close = raw[symbol]["Close"]
                    else:
                        close = raw["Close"][symbol]
                else:
                    close = raw["Close"]
            except (KeyError, TypeError):
                logger.warning("Yahoo sem Close para %s", symbol)
                continue
            frame = pd.DataFrame(
                {
                    "Data": pd.to_datetime(close.index).tz_localize(None).normalize(),
                    "Ticker": _normalize_ticker(symbol),
                    "Adjusted_Close": pd.to_numeric(close, errors="coerce").values,
                    "Fonte": "yahoo_auto_adjust",
                }
            ).dropna(subset=["Adjusted_Close"])
            if not frame.empty:
                frames.append(frame)
    return prepare_prices(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame(columns=PRICE_COLUMNS)


def merge_price_cache(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    frames = [frame for frame in (existing, new) if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    return prepare_prices(pd.concat(frames, ignore_index=True, sort=False))

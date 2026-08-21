"""
backtest.py — Camada 3: Backtest

Responsabilidades atuais:
1. Registrar diariamente a carteira Top 20 recomendada em Parquet.
2. Manter o backtest legado de FIIs contra IFIX e IBOV via yfinance.

A primeira responsabilidade é a mais importante neste momento, porque cria a
base histórica necessária para avaliar as recomendações no futuro.
"""

import logging
import os
from datetime import timedelta

import pandas as pd

logger = logging.getLogger(__name__)

BENCHMARK_YAHOO = {
    "IFIX": "XFIX11.SA",
    "IBOV": "^BVSP",
}

# Nomes de coluna aceitos por tipo de ativo.
# As fontes variam a acentuação entre execuções e entre Excel/Parquet,
# então cada candidato é testado em ordem.
_TICKER_COLS = {
    "FII": ("FUNDOS",),
    "ACAO": ("Ação", "Acao", "AÇÃO", "Ticker"),
}

_PRICE_COLS = {
    "FII": ("PREÇO ATUAL (R$)", "Preço", "Preco", "Preço Atual"),
    "ACAO": ("Preço", "Preco", "PREÇO ATUAL (R$)"),
}


def _first_present(row: pd.Series, candidates) -> str | None:
    """Retorna o primeiro nome de coluna presente e não nulo na linha."""
    for col in candidates:
        if col in row.index and pd.notna(row[col]):
            return col
    return None


def _portfolio_rows(df: pd.DataFrame, tipo: str, data_execucao: str) -> list[dict]:
    """Converte um Top N em linhas da carteira histórica.

    Além do ticker, preserva Preco_Entrada, Score e Posicao — sem o preço de
    entrada a carteira não serve para backtest.
    """
    if df is None or df.empty:
        return []

    rows = []
    posicao = 0

    for _, row in df.iterrows():
        ticker_col = _first_present(row, _TICKER_COLS[tipo])

        if ticker_col is None:
            continue

        posicao += 1
        price_col = _first_present(row, _PRICE_COLS[tipo])

        rows.append(
            {
                "Data_Carteira": str(data_execucao),
                "Tipo": tipo,
                "Ticker": str(row[ticker_col]).strip().upper(),
                "Preco_Entrada": (
                    pd.to_numeric(row[price_col], errors="coerce")
                    if price_col
                    else pd.NA
                ),
                "Score": pd.to_numeric(row.get("Score"), errors="coerce"),
                "Posicao": posicao,
            }
        )

    if not rows:
        logger.warning(
            "Nenhum ticker %s reconhecido na carteira de %s — "
            "colunas disponíveis: %s",
            tipo,
            data_execucao,
            list(df.columns)[:10],
        )

    return rows


def save_portfolio_snapshot(
    top_fiis: pd.DataFrame,
    top_acoes: pd.DataFrame,
    data_execucao: str,
    output_file: str,
):
    """
    Salva a composição histórica da carteira.

    Para uma determinada data, a carteira anterior daquele mesmo dia
    é completamente substituída. Isso evita acumular ativos de
    execuções anteriores do workflow.
    """

    rows = (
        _portfolio_rows(top_fiis, "FII", data_execucao)
        + _portfolio_rows(top_acoes, "ACAO", data_execucao)
    )

    novo_df = pd.DataFrame(
        rows,
        columns=[
            "Data_Carteira",
            "Tipo",
            "Ticker",
            "Preco_Entrada",
            "Score",
            "Posicao",
        ],
    )

    # ============================================================
    # CARREGA HISTÓRICO EXISTENTE
    # ============================================================

    if os.path.exists(output_file):
        historico = pd.read_parquet(output_file)

        # Remove TODA a carteira da data atual.
        #
        # Isso é intencional:
        # se o workflow rodar duas vezes no mesmo dia e a seleção
        # mudar, a segunda execução substitui completamente a primeira.
        historico = historico[
            historico["Data_Carteira"].astype(str)
            != str(data_execucao)
        ].copy()

        historico = pd.concat(
            [
                historico,
                novo_df,
            ],
            ignore_index=True,
        )

    else:
        historico = novo_df

    # ============================================================
    # REMOVE DUPLICIDADES
    # ============================================================

    historico = historico.drop_duplicates(
        subset=[
            "Data_Carteira",
            "Tipo",
            "Ticker",
        ],
        keep="last",
    )

    # ============================================================
    # SALVA
    # ============================================================

    output_dir = os.path.dirname(output_file)

    if output_dir:
        os.makedirs(
            output_dir,
            exist_ok=True,
        )

    historico.to_parquet(
        output_file,
        index=False,
    )

    logger.info(
        "Carteira histórica salva: %s (%s linhas — %s FII, %s ACAO)",
        output_file,
        len(historico),
        sum(1 for r in rows if r["Tipo"] == "FII"),
        sum(1 for r in rows if r["Tipo"] == "ACAO"),
    )


def _yahoo_ticker(fii: str) -> str:
    return f"{str(fii).strip().upper()}.SA"


def _resolve_date_col(df: pd.DataFrame) -> str | None:
    for col in ("Data Preco", "Data Preço", "data_preco", "Data_Execucao"):
        if col in df.columns:
            return col
    return None


def load_top20_snapshots(hist_path: str) -> list[tuple[pd.Timestamp, list[str]]]:
    """Carrega snapshots diários do Top 20 FIIs a partir do histórico Excel."""
    try:
        df = pd.read_excel(hist_path)
    except FileNotFoundError:
        logger.warning("Historico Top 20 nao encontrado: %s", hist_path)
        return []
    except Exception as e:
        logger.warning("Falha ao ler historico Top 20: %s", e)
        return []

    date_col = _resolve_date_col(df)
    if date_col is None or "FUNDOS" not in df.columns:
        logger.warning("Historico Top 20 sem colunas esperadas (FUNDOS / Data Preco)")
        return []

    df = df.dropna(subset=["FUNDOS"]).copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    snapshots = []
    for date, group in df.groupby(date_col):
        tickers = (
            group["FUNDOS"]
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .unique()
            .tolist()
        )
        if tickers:
            snapshots.append((pd.Timestamp(date).normalize(), tickers))

    snapshots.sort(key=lambda item: item[0])
    return snapshots


def _fetch_close_series(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Retorna série de preços de fechamento ajustado entre start e end."""
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance nao instalado — backtest indisponivel")
        return pd.Series(dtype=float)

    if end <= start:
        return pd.Series(dtype=float)

    end_inclusive = end + timedelta(days=1)
    raw = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end_inclusive.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )

    if raw.empty:
        return pd.Series(dtype=float)

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)

    close = pd.to_numeric(raw["Close"], errors="coerce").dropna()
    close.index = pd.to_datetime(close.index).normalize()
    return close.sort_index()


def _return_pct(series: pd.Series) -> float | None:
    if series.empty or len(series) < 2:
        return None

    start_val = float(series.iloc[0])
    end_val = float(series.iloc[-1])

    if start_val == 0:
        return None

    return (end_val / start_val) - 1.0


def _asset_return(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    return _return_pct(_fetch_close_series(ticker, start, end))


def _portfolio_return(tickers: list[str], start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    returns = []

    for ticker in tickers:
        ret = _asset_return(_yahoo_ticker(ticker), start, end)
        if ret is not None:
            returns.append(ret)

    if not returns:
        return None

    return sum(returns) / len(returns)


def _chain_base100(base100: float, period_return: float | None) -> float:
    if period_return is None:
        return base100
    return base100 * (1.0 + period_return)


def run_backtest(hist_path: str, data_fim: str | None = None) -> dict:
    """
    Executa backtest legado da carteira Top 20 FIIs vs IFIX e IBOV.

    Returns:
        dict com retornos acumulados, flags bateu_ifix/bateu_ibov e detalhe por período.
    """
    snapshots = load_top20_snapshots(hist_path)
    if not snapshots:
        return {
            "disponivel": False,
            "motivo": "Historico Top 20 FIIs insuficiente para backtest",
        }

    fim = pd.Timestamp(data_fim).normalize() if data_fim else pd.Timestamp.today().normalize()

    cart_base100 = 100.0
    ifix_base100 = 100.0
    ibov_base100 = 100.0
    periodos = []
    periodos_com_dados = 0

    for i, (start, tickers) in enumerate(snapshots):
        end = snapshots[i + 1][0] if i + 1 < len(snapshots) else fim
        if end <= start:
            continue

        cart_ret = _portfolio_return(tickers, start, end)
        ifix_ret = _asset_return(BENCHMARK_YAHOO["IFIX"], start, end)
        ibov_ret = _asset_return(BENCHMARK_YAHOO["IBOV"], start, end)

        if cart_ret is None:
            logger.warning("Backtest: sem retorno da carteira em %s -> %s", start.date(), end.date())
            continue

        periodos_com_dados += 1
        cart_base100 = _chain_base100(cart_base100, cart_ret)
        ifix_base100 = _chain_base100(ifix_base100, ifix_ret)
        ibov_base100 = _chain_base100(ibov_base100, ibov_ret)

        periodos.append(
            {
                "inicio": start.strftime("%Y-%m-%d"),
                "fim": end.strftime("%Y-%m-%d"),
                "ativos": len(tickers),
                "carteira_retorno_pct": round(cart_ret * 100, 2),
                "ifix_retorno_pct": round(ifix_ret * 100, 2) if ifix_ret is not None else None,
                "ibov_retorno_pct": round(ibov_ret * 100, 2) if ibov_ret is not None else None,
            }
        )

    if periodos_com_dados == 0:
        return {
            "disponivel": False,
            "motivo": "Nao foi possivel calcular retorno da carteira Top 20",
        }

    bateu_ifix = cart_base100 > ifix_base100 if periodos else None
    bateu_ibov = cart_base100 > ibov_base100 if periodos else None

    result = {
        "disponivel": True,
        "periodo": {
            "inicio": snapshots[0][0].strftime("%Y-%m-%d"),
            "fim": fim.strftime("%Y-%m-%d"),
        },
        "rebalanceamentos": len(snapshots),
        "carteira_top20_fiis": {
            "retorno_pct": round(cart_base100 - 100, 2),
            "base100": round(cart_base100, 2),
        },
        "ifix": {
            "retorno_pct": round(ifix_base100 - 100, 2),
            "base100": round(ifix_base100, 2),
        },
        "ibov": {
            "retorno_pct": round(ibov_base100 - 100, 2),
            "base100": round(ibov_base100, 2),
        },
        "bateu_ifix": bateu_ifix,
        "bateu_ibov": bateu_ibov,
        "periodos": periodos,
        "metodologia": (
            "Camada 3 — carteira equal-weight Top 20 FIIs rebalanceada a cada snapshot "
            "diário, comparada a IFIX (XFIX11.SA) e IBOV (^BVSP) via yfinance."
        ),
    }

    logger.info(
        "Backtest Top20 FIIs: carteira=%+.2f%%, IFIX=%+.2f%%, IBOV=%+.2f%% — "
        "bateu IFIX=%s, bateu IBOV=%s",
        result["carteira_top20_fiis"]["retorno_pct"],
        result["ifix"]["retorno_pct"],
        result["ibov"]["retorno_pct"],
        bateu_ifix,
        bateu_ibov,
    )

    return result

"""benchmark.py — Coleta benchmarks em valor absoluto para o dashboard.

Fontes gratuitas:
- Yahoo Finance/yfinance: IBOV (^BVSP), IFIX proxy (XFIX11.SA), IMOB (IMOB.SA)
- BCB SGS: IPCA (433), IGP-M (189), CDI diário (12)

Observação: séries do BCB que vêm como variação percentual são acumuladas em
base 100 para permitir comparação visual de crescimento.
"""

import logging
from datetime import datetime, timedelta

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BCB_SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

YAHOO_TICKERS = {
    "IBOV": "^BVSP",
    "IFIX": "XFIX11.SA",
    "IMOB": "IMOB.SA",
}

BCB_SERIES = {
    "IPCA": 433,
    "IGPM": 189,
    "CDI": 12,
}


def _fetch_yahoo(ticker: str, nome: str, meses: int = 13) -> pd.DataFrame:
    """Busca série histórica do Yahoo Finance como valor absoluto."""
    try:
        import yfinance as yf

        end = datetime.today() + timedelta(days=1)
        start = end - timedelta(days=meses * 31)

        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
        )

        if df.empty:
            logger.warning(f"{nome} ({ticker}): sem dados no yfinance")
            return pd.DataFrame(columns=["data", "valor"])

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        if "Close" not in df.columns:
            logger.warning(f"{nome} ({ticker}): coluna Close ausente")
            return pd.DataFrame(columns=["data", "valor"])

        df = df[["Close"]].rename(columns={"Close": "valor"})
        df.index.name = "data"
        df = df.reset_index()
        df["data"] = pd.to_datetime(df["data"])
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.dropna(subset=["valor"]).reset_index(drop=True)

        logger.info(f"{nome} ({ticker}): {len(df)} pontos OK")
        return df

    except Exception as e:
        logger.warning(f"{nome} ({ticker}): falha no yfinance — {e}")
        return pd.DataFrame(columns=["data", "valor"])


def _fetch_bcb(codigo: int, meses: int = 13) -> pd.DataFrame:
    """Busca série temporal do BCB SGS."""
    try:
        data_inicio = (datetime.today() - timedelta(days=meses * 31)).strftime("%d/%m/%Y")
        url = f"{BCB_SGS_URL.format(codigo=codigo)}?formato=json&dataInicial={data_inicio}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            return pd.DataFrame(columns=["data", "valor"])

        df = pd.DataFrame(data)
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.dropna(subset=["valor"]).sort_values("data").reset_index(drop=True)
        return df

    except Exception as e:
        logger.warning(f"Falha ao buscar BCB serie {codigo}: {e}")
        return pd.DataFrame(columns=["data", "valor"])


def _acumular_base100(df: pd.DataFrame) -> pd.DataFrame:
    """Converte variações percentuais em índice acumulado base 100."""
    if df.empty:
        return pd.DataFrame(columns=["data", "valor"])

    df = df.copy()
    df["taxa"] = pd.to_numeric(df["valor"], errors="coerce") / 100
    df["valor"] = 100.0 * (1 + df["taxa"]).cumprod()
    return df[["data", "valor"]].dropna(subset=["valor"]).reset_index(drop=True)


def get_benchmarks(meses: int = 13) -> dict:
    """Coleta todos os benchmarks usados no dashboard."""
    logger.info("Coletando benchmarks...")
    result = {}

    for nome, ticker in YAHOO_TICKERS.items():
        result[nome] = _fetch_yahoo(ticker, nome, meses)

    for nome, codigo in BCB_SERIES.items():
        df_raw = _fetch_bcb(codigo, meses)
        result[nome] = _acumular_base100(df_raw)
        logger.info(
            f"  {nome} (BCB {codigo}): {len(result[nome])} pontos "
            f"{'OK' if not result[nome].empty else 'VAZIO'}"
        )

    for nome in list(YAHOO_TICKERS.keys()):
        df = result.get(nome, pd.DataFrame())
        logger.info(f"  {nome}: {len(df)} pontos {'OK' if not df.empty else 'VAZIO'}")

    return result


def _serie_to_records(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []

    return [
        {
            "data": pd.to_datetime(r["data"]).strftime("%Y-%m-%d"),
            "valor": round(float(r["valor"]), 4) if pd.notna(r["valor"]) else None,
        }
        for _, r in df.iterrows()
    ]


def benchmarks_to_json(benchmarks: dict) -> dict:
    return {nome: _serie_to_records(df) for nome, df in (benchmarks or {}).items()}

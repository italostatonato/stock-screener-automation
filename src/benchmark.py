"""
benchmark.py

Coleta benchmarks em VALOR ABSOLUTO via yfinance e BCB SGS:
- IBOV  -> yfinance ^BVSP (Ibovespa em pontos)
- IFIX  -> yfinance XFIX11.SA (ETF proxy do IFIX)
- IPCA  -> BCB SGS serie 433 (variacao mensal -> acumulado base 100)
- IGP-M -> BCB SGS serie 189 (variacao mensal -> acumulado base 100)

Todos os valores sao retornados em valor absoluto — nunca variacao percentual.
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
}

BCB_SERIES = {
    "IPCA": 433,
    "IGPM": 189,
}


def _fetch_yahoo(ticker: str, nome: str, meses: int = 13) -> pd.DataFrame:
    """Busca serie historica do Yahoo Finance como valor absoluto."""
    try:
        import yfinance as yf
        end = datetime.today()
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
    """Busca serie temporal do BCB SGS."""
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
    """Converte variacoes mensais (%) em indice acumulado base 100."""
    if df.empty:
        return df
    df = df.copy()
    df["taxa"] = df["valor"] / 100
    df["valor"] = 100.0 * (1 + df["taxa"]).cumprod()
    return df[["data", "valor"]]


def get_benchmarks(meses: int = 13) -> dict:
    """
    Coleta todos os benchmarks em VALOR ABSOLUTO.

    Returns:
        dict com DataFrames (data, valor):
        IBOV (pontos ^BVSP), IFIX (pontos XFIX11.SA),
        IPCA (base 100), IGPM (base 100)
    """
    logger.info("Coletando benchmarks...")
    result = {}

    for nome, ticker in YAHOO_TICKERS.items():
        result[nome] = _fetch_yahoo(ticker, nome, meses)

    for nome, codigo in BCB_SERIES.items():
        df_raw = _fetch_bcb(codigo, meses)
        result[nome] = _acumular_base100(df_raw) if not df_raw.empty else pd.DataFrame(columns=["data", "valor"])
        logger.info(f"  {nome} (BCB {codigo}): {len(result[nome])} pontos {'OK' if not result[nome].empty else 'VAZIO'}")

    for nome in ["IBOV", "IFIX"]:
        df = result.get(nome, pd.DataFrame())
        logger.info(f"  {nome}: {len(df)} pontos {'OK' if not df.empty else 'VAZIO'}")

    return result


def _serie_to_records(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []
    return [
        {
            "data": r["data"].strftime("%Y-%m-%d"),
            "valor": round(float(r["valor"]), 2) if pd.notna(r["valor"]) else None,
        }
        for _, r in df.iterrows()
    ]


def benchmarks_to_json(benchmarks: dict) -> dict:
    return {nome: _serie_to_records(df) for nome, df in benchmarks.items()}

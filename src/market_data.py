import logging
import requests
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Códigos das séries do Banco Central (SGS)
BCB_SERIES = {
    "IPCA (12 meses)": 433,       # IPCA mensal — acumulamos 12 meses
    "Selic Meta": 432,
    "Dólar (PTAX venda)": 1,
    "IGP-M": 189,
}

BCB_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"


def _fetch_bcb_series(codigo: int, meses: int = 13) -> pd.DataFrame:
    """Busca uma série temporal do BCB (SGS) dos últimos N meses."""
    data_inicio = (datetime.today() - timedelta(days=meses * 31)).strftime("%d/%m/%Y")
    url = f"{BCB_URL.format(codigo=codigo)}?formato=json&dataInicial={data_inicio}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data)
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df
    except Exception as e:
        logger.warning(f"Falha ao buscar série BCB {codigo}: {e}")
        return pd.DataFrame(columns=["data", "valor"])


def _fetch_awesome_api(pares: list) -> dict:
    """Busca cotações de câmbio/commodities via AwesomeAPI (gratuita, sem chave)."""
    codigos = ",".join(pares)
    url = f"https://economia.awesomeapi.com.br/json/last/{codigos}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Falha ao buscar AwesomeAPI: {e}")
        return {}


def get_market_indicators() -> dict:
    """
    Coleta os principais indicadores de mercado.

    Returns:
        dict com:
        - 'ipca_12m': DataFrame histórico mensal do IPCA
        - 'selic': DataFrame histórico da Selic
        - 'igpm': DataFrame histórico do IGP-M
        - 'cambio': dict com cotações atuais (USD, EUR, GBP) + variação do dia
        - 'ouro': dict com cotação atual do ouro
    """
    logger.info("Coletando indicadores de mercado...")
    result = {}

    # ── IPCA, Selic, IGP-M (BCB) ────────────────────────────────────────────
    result["ipca_12m"] = _fetch_bcb_series(BCB_SERIES["IPCA (12 meses)"], meses=13)
    result["selic"]    = _fetch_bcb_series(BCB_SERIES["Selic Meta"], meses=13)
    result["igpm"]     = _fetch_bcb_series(BCB_SERIES["IGP-M"], meses=13)

    # ── Câmbio e Ouro (AwesomeAPI) ───────────────────────────────────────────
    pares = ["USD-BRL", "EUR-BRL", "GBP-BRL", "BTC-BRL"]
    cambio_raw = _fetch_awesome_api(pares)

    cambio = {}
    for par, dados in cambio_raw.items():
        try:
            cambio[dados["code"] + "/" + dados["codein"]] = {
                "valor": float(dados["bid"]),
                "variacao_pct": float(dados["pctChange"]),
                "atualizado_em": dados.get("create_date", ""),
            }
        except (KeyError, ValueError):
            continue

    result["cambio"] = cambio

    logger.info(f"Indicadores coletados: IPCA={len(result['ipca_12m'])} pts, "
                f"Selic={len(result['selic'])} pts, Câmbio={len(cambio)} pares")
    return result
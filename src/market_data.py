from datetime import datetime, timedelta
import logging
import time

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Códigos das séries do Banco Central (SGS)
BCB_SERIES = {
    "IPCA (12 meses)": 13522,
    "Selic Meta": 432,
    "Dólar (PTAX venda)": 1,
    "IGP-M": 189,
}

BCB_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"


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
        df["valor"] = pd.to_numeric(
            df["valor"].astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        )
        # Algumas séries podem conter observações programadas pelo provedor.
        # Indicadores futuros distorcem o eixo do gráfico e não devem compor
        # um snapshot histórico já publicado.
        hoje = pd.Timestamp(datetime.today().date())
        return (
            df[df["data"] <= hoje]
            .dropna(subset=["data", "valor"])
            .sort_values("data")
            .drop_duplicates(subset=["data"], keep="last")
            .reset_index(drop=True)
        )
    except Exception as e:
        logger.warning(f"Falha ao buscar série BCB {codigo}: {e}")
        return pd.DataFrame(columns=["data", "valor"])


def _fetch_awesome_api(pares: list) -> dict:
    """Busca cotações de câmbio/commodities via AwesomeAPI (gratuita, sem chave)."""
    codigos = ",".join(pares)
    url = f"https://economia.awesomeapi.com.br/json/last/{codigos}"
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Radar-Semanal/1.0"})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Falha ao buscar AwesomeAPI: {e}")
        # Alguns limites do provedor afetam consultas em lote. Tentar cada par
        # isoladamente mantém o painel útil sem transformar uma falha parcial
        # em uma seção inteira vazia.
        fallback = {}
        for par in pares:
            try:
                item_url = f"https://economia.awesomeapi.com.br/json/last/{par}"
                resp = requests.get(
                    item_url,
                    timeout=15,
                    headers={"User-Agent": "Radar-Semanal/1.0"},
                )
                resp.raise_for_status()
                payload = resp.json()
                if isinstance(payload, dict):
                    fallback.update(payload)
            except Exception as item_error:
                logger.warning("Falha ao buscar %s na AwesomeAPI: %s", par, item_error)
        return fallback


def _fetch_coingecko_top_cryptos(limit: int = 5) -> list[dict]:
    """Busca as maiores criptomoedas por valor de mercado, com preços em BRL.

    O endpoint público da CoinGecko é adequado ao processamento semanal e pode
    responder 429 em momentos de pico. O pequeno backoff evita descartar a
    seção por uma limitação transitória.
    """
    params = {
        "vs_currency": "brl",
        "order": "market_cap_desc",
        "per_page": max(1, min(int(limit), 20)),
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
        "locale": "pt",
    }
    for attempt in range(3):
        try:
            resp = requests.get(
                COINGECKO_MARKETS_URL,
                params=params,
                timeout=20,
                headers={"User-Agent": "Radar-Semanal/1.0"},
            )
            if resp.status_code == 429 and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, list):
                raise ValueError("resposta não é uma lista")

            cryptos = []
            for item in payload[:limit]:
                try:
                    cryptos.append(
                        {
                            "id": str(item.get("id") or ""),
                            "simbolo": str(item.get("symbol") or "").upper(),
                            "nome": str(item.get("name") or ""),
                            "ranking_market_cap": int(item["market_cap_rank"]),
                            "preco_brl": float(item["current_price"]),
                            "variacao_24h_pct": (
                                float(item["price_change_percentage_24h"])
                                if item.get("price_change_percentage_24h") is not None
                                else None
                            ),
                            "market_cap_brl": (
                                float(item["market_cap"])
                                if item.get("market_cap") is not None
                                else None
                            ),
                            "imagem": str(item.get("image") or ""),
                            "atualizado_em": str(item.get("last_updated") or ""),
                        }
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            return cryptos
        except Exception as e:
            logger.warning(
                "Falha ao buscar top cripto na CoinGecko (tentativa %s): %s",
                attempt + 1,
                e,
            )
            if attempt < 2:
                time.sleep(2 ** attempt)
    return []


def get_market_indicators() -> dict:
    """
    Coleta os principais indicadores de mercado.

    Returns:
        dict com:
        - 'ipca_12m': DataFrame histórico mensal do IPCA
        - 'selic': DataFrame histórico da Selic
        - 'igpm': DataFrame histórico do IGP-M
        - 'cambio': dict com cotações atuais (USD, EUR, GBP) + variação do dia
        - 'cripto': cinco maiores criptomoedas por valor de mercado, em BRL
    """
    logger.info("Coletando indicadores de mercado...")
    result = {}

    # ── IPCA, Selic, IGP-M (BCB) ────────────────────────────────────────────
    result["ipca_12m"] = _fetch_bcb_series(BCB_SERIES["IPCA (12 meses)"], meses=13)
    result["selic"]    = _fetch_bcb_series(BCB_SERIES["Selic Meta"], meses=13)
    result["igpm"]     = _fetch_bcb_series(BCB_SERIES["IGP-M"], meses=13)

    # ── Câmbio (AwesomeAPI) e cripto (CoinGecko) ─────────────────────────────
    pares = ["USD-BRL", "EUR-BRL", "GBP-BRL"]
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
    result["cripto"] = _fetch_coingecko_top_cryptos(limit=5)

    logger.info(f"Indicadores coletados: IPCA={len(result['ipca_12m'])} pts, "
                f"Selic={len(result['selic'])} pts, Câmbio={len(cambio)} pares, "
                f"Cripto={len(result['cripto'])} ativos")
    return result

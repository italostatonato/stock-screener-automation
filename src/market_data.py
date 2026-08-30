from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
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
FRANKFURTER_LATEST_URL = "https://api.frankfurter.dev/v1/latest"
BRAPI_QUOTE_LIST_URL = "https://brapi.dev/api/quote/list"
YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"


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


def _fetch_frankfurter_cambio() -> dict:
    """Fallback diário de câmbio quando a AwesomeAPI não responde.

    A Frankfurter devolve quantas unidades de moeda estrangeira equivalem a
    BRL 1. O dashboard precisa do inverso: quantos reais valem uma unidade de
    USD, EUR ou GBP.
    """
    try:
        resp = requests.get(
            FRANKFURTER_LATEST_URL,
            params={"base": "BRL", "symbols": "USD,EUR,GBP"},
            timeout=15,
            headers={"User-Agent": "Radar-Semanal/1.0"},
        )
        resp.raise_for_status()
        payload = resp.json()
        rates = payload.get("rates", {}) if isinstance(payload, dict) else {}
        updated_at = str(payload.get("date") or "") if isinstance(payload, dict) else ""
        cambio = {}
        for currency in ("USD", "EUR", "GBP"):
            rate = float(rates.get(currency) or 0)
            if rate <= 0:
                continue
            cambio[f"{currency}/BRL"] = {
                "valor": 1 / rate,
                "variacao_pct": None,
                "atualizado_em": updated_at,
                "fonte": "Frankfurter",
            }
        return cambio
    except Exception as exc:
        logger.warning("Falha ao buscar câmbio na Frankfurter: %s", exc)
        return {}


def _asset_name_from_brapi(ticker: str) -> str | None:
    """Tenta obter o nome cadastral do ativo na listagem pública da brapi."""
    try:
        resp = requests.get(
            BRAPI_QUOTE_LIST_URL,
            params={"search": ticker, "limit": 5},
            timeout=12,
            headers={"User-Agent": "Radar-Semanal/1.0"},
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("stocks", []) if isinstance(payload, dict) else []
        exact = next(
            (
                row for row in rows
                if str(row.get("stock") or "").strip().upper() == ticker
            ),
            None,
        )
        name = str((exact or {}).get("name") or "").strip()
        return name if name and name.upper() != ticker else None
    except Exception:
        return None


def _asset_name_from_yahoo(ticker: str) -> str | None:
    """Complementa nomes ausentes, sobretudo a denominação dos FIIs."""
    try:
        symbol = f"{ticker}.SA"
        resp = requests.get(
            YAHOO_SEARCH_URL,
            params={"q": symbol, "quotesCount": 5, "newsCount": 0},
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (Radar-Semanal/1.0)"},
        )
        resp.raise_for_status()
        payload = resp.json()
        quotes = payload.get("quotes", []) if isinstance(payload, dict) else []
        exact = next(
            (
                row for row in quotes
                if str(row.get("symbol") or "").strip().upper() == symbol
            ),
            None,
        )
        name = str(
            (exact or {}).get("longname")
            or (exact or {}).get("shortname")
            or ""
        ).strip()
        return name if name and name.upper() not in {ticker, symbol} else None
    except Exception:
        return None


def _fetch_asset_names(tickers: list[str], workers: int = 8) -> dict[str, str]:
    """Resolve nomes completos dos ativos sem tornar a coleta obrigatória.

    O nome da brapi é preferido para ações. Quando a listagem retorna apenas o
    ticker (comum em FIIs), a busca pública do Yahoo Finance complementa o
    cadastro. Falhas individuais não interrompem o processamento semanal.
    """
    normalized = sorted(
        {
            str(ticker or "").strip().upper()
            for ticker in tickers or []
            if str(ticker or "").strip()
        }
    )
    if not normalized:
        return {}

    def resolve(ticker: str) -> tuple[str, str | None]:
        return ticker, _asset_name_from_brapi(ticker) or _asset_name_from_yahoo(ticker)

    names: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(normalized)))) as pool:
        futures = [pool.submit(resolve, ticker) for ticker in normalized]
        for future in as_completed(futures):
            ticker, name = future.result()
            if name:
                names[ticker] = name
    return names


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


def get_market_indicators(asset_tickers: list[str] | None = None) -> dict:
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

    if len(cambio) < len(pares):
        for pair, data in _fetch_frankfurter_cambio().items():
            cambio.setdefault(pair, data)

    result["cambio"] = cambio
    result["cripto"] = _fetch_coingecko_top_cryptos(limit=5)
    result["asset_names"] = _fetch_asset_names(asset_tickers or [])

    logger.info(f"Indicadores coletados: IPCA={len(result['ipca_12m'])} pts, "
                f"Selic={len(result['selic'])} pts, Câmbio={len(cambio)} pares, "
                f"Cripto={len(result['cripto'])} ativos, "
                f"Nomes={len(result['asset_names'])} ativos")
    return result

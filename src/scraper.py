import time
import logging
import re
import unicodedata
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
from pathlib import Path
from typing import Any, Iterable
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import os
import requests

logger = logging.getLogger(__name__)


def _normalized_column_name(name: Any) -> str:
    """Normaliza cabeçalhos de fontes externas para comparação estável."""
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _fundamentus_column(df: pd.DataFrame, *aliases: str) -> str:
    """Encontra uma coluna do Fundamentus, tolerando acentos e pontuação."""
    normalized = {_normalized_column_name(col): col for col in df.columns}
    for alias in aliases:
        found = normalized.get(_normalized_column_name(alias))
        if found:
            return found
    raise ValueError(
        "Coluna esperada não encontrada na tabela do Fundamentus: "
        f"{', '.join(aliases)}. Colunas recebidas: {list(df.columns)}"
    )


def _parse_fundamentus_number(value: Any, percent: bool = False) -> float | None:
    """Converte a notação brasileira da tabela pública do Fundamentus."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value) / 100 if percent else float(value)

    text = str(value).strip().replace("R$", "").replace("%", "").strip()
    if text in {"", "-", "N/A", "nan"}:
        return None

    # A fonte usa ponto para milhar e vírgula para decimal. Também aceitamos
    # números que já venham com ponto decimal após uma mudança do HTML.
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")

    try:
        numeric = float(text)
    except ValueError:
        return None
    return numeric / 100 if percent else numeric


def _fundamentus_series(
    df: pd.DataFrame,
    *aliases: str,
    percent: bool = False,
) -> pd.Series:
    """Retorna uma coluna do Fundamentus convertida para valor numérico."""
    column = _fundamentus_column(df, *aliases)
    return df[column].map(lambda value: _parse_fundamentus_number(value, percent))


def _safe_series_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, pd.NA)
    return numerator / denominator


def build_fundamentus_acoes_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Mapeia a tabela pública do Fundamentus ao contrato do screener.

    O Fundamentus publica ROIC, ROE, liquidez de dois meses e dívida líquida
    sobre patrimônio. O ROA é obtido por (P/Ativo) / (P/L), identidade que
    equivale a lucro líquido / ativo total. O valor de mercado é P/VP vezes o
    patrimônio líquido. Esses cálculos preservam unidades decimais (0,10=10%).
    """
    if raw is None or raw.empty:
        raise RuntimeError("A tabela pública do Fundamentus veio vazia.")

    acao = _fundamentus_column(raw, "Papel")
    preco = _fundamentus_series(raw, "Cotação", "Cotacao")
    pl = _fundamentus_series(raw, "P/L")
    pvp = _fundamentus_series(raw, "P/VP")
    pativo = _fundamentus_series(raw, "P/Ativo")
    patrimonio = _fundamentus_series(raw, "Patrim. Líq", "Patrim. Liq")
    divida_liquida_pl = _fundamentus_series(
        raw, "Dív.Líq/ Patrim.", "Div.Liq/ Patrim.",
    )

    frame = pd.DataFrame({
        "Ação": raw[acao].astype(str).str.strip().str.upper(),
        # A tabela é por papel; usar o ticker aqui evita eliminar classes
        # diferentes da mesma companhia antes da aplicação dos filtros.
        "Empresa": raw[acao].astype(str).str.strip().str.upper(),
        "Preço": preco,
        "Preço/VPA": pvp,
        "Preço/Lucro": pl,
        "EV/EBIT": _fundamentus_series(raw, "EV/EBIT"),
        "EV/EBITDA": _fundamentus_series(raw, "EV/EBITDA"),
        "Margem Líquida": _fundamentus_series(raw, "Mrg. Líq.", "Mrg Liq", percent=True),
        "ROA": _safe_series_ratio(pativo, pl),
        "RPL": _fundamentus_series(raw, "ROE", percent=True),
        "ROInvC": _fundamentus_series(raw, "ROIC", percent=True),
        # A fonte divulga dívida líquida/PL, não passivo total/PL. A coluna
        # legada é mantida para o contrato do dashboard e documentada no README.
        "Passivo/Patrimônio Líquido": divida_liquida_pl,
        "Alavancagem Financeira": 1 + divida_liquida_pl,
        "Dividend Yield": _fundamentus_series(raw, "Div.Yield", "Div Yield", percent=True),
        "Volume Diário Médio (3 meses)": _fundamentus_series(raw, "Liq.2meses", "Liq. 2meses"),
        "Market Cap Empresa": pvp * patrimonio,
        "Fonte Dados": "Fundamentus (tabela pública)",
    })

    frame = frame.replace([float("inf"), float("-inf")], pd.NA)
    frame = frame[frame["Ação"].str.fullmatch(r"[A-Z]{4}\d{1,2}", na=False)]
    frame = frame[frame["Preço"].notna() & (frame["Preço"] > 0)]
    return frame.reset_index(drop=True)


def scrape_acoes_fundamentus(cfg: dict) -> pd.DataFrame:
    """Lê a tabela pública do Fundamentus com retentativas transitórias."""
    url = str(cfg.get("fundamentus_url", "https://www.fundamentus.com.br/resultado.php"))
    timeout = float(cfg.get("fundamentus_timeout", 30))
    retries = max(0, int(cfg.get("fundamentus_retries", 2)))
    headers = {
        "User-Agent": "stock-screener-automation/1.0 (coleta semanal; dados públicos)",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }

    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            # A tabela usa ponto para milhar e vírgula para decimal. Sem esses
            # parâmetros, o parser padrão transforma P/VP 0,75 em 75.
            tables = pd.read_html(
                StringIO(response.text),
                decimal=",",
                thousands=".",
            )
            break
        except (requests.RequestException, ValueError) as exc:
            if attempt < retries:
                wait_seconds = 2 ** attempt
                logger.warning(
                    "Fundamentus indisponível (tentativa %d/%d); nova tentativa em %ds.",
                    attempt + 1,
                    retries + 1,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue
            raise RuntimeError(
                "Falha ao ler a tabela pública de ações do Fundamentus. "
                "A fonte pode estar indisponível ou ter alterado o formato."
            ) from exc

    for table in tables:
        normalized = {_normalized_column_name(col) for col in table.columns}
        if "papel" in normalized and "pl" in normalized and "pvp" in normalized:
            frame = build_fundamentus_acoes_frame(table)
            if frame.empty:
                raise RuntimeError("Fundamentus retornou tabela, mas sem ações válidas.")
            logger.info("Ações Fundamentus coletadas: %d linhas x %d colunas", *frame.shape)
            return frame

    raise RuntimeError("Não foi localizada a tabela de ações esperada no Fundamentus.")


def scrape_acoes(cfg: dict) -> pd.DataFrame:
    """Despacha a coleta configurada, mantendo a fonte paga apenas opcional."""
    source = str(cfg.get("acoes_source", "fundamentus")).strip().lower()
    if source == "fundamentus":
        return scrape_acoes_fundamentus(cfg)
    if source == "brapi":
        return scrape_acoes_brapi(cfg)
    if source == "investsite":
        return scrape_acoes_investsite(cfg)
    raise ValueError(
        "Fonte de ações inválida. Use 'fundamentus', 'brapi' ou 'investsite'."
    )


def _load_page(driver, url: str, timeout: float) -> None:
    """Carrega a página sem deixar recursos secundários travarem o scraper."""
    driver.set_page_load_timeout(timeout)
    try:
        driver.get(url)
    except TimeoutException:
        # A tabela pode já estar disponível mesmo que anúncios ou trackers
        # mantenham a navegação pendente. Interrompemos esses recursos e a
        # validação abaixo decide se a tabela realmente carregou.
        logger.warning("Timeout ao carregar %s; interrompendo recursos pendentes.", url)
        driver.execute_script("window.stop();")


def _raise_if_investsite_login_required(driver) -> None:
    """Interrompe a coleta com uma causa útil quando o site exige sessão."""
    current_url = str(getattr(driver, "current_url", "")).lower()
    if "investsite.com.br/login" not in current_url:
        return

    raise PermissionError(
        "O Investsite redirecionou a coleta para a página de login. "
        "A automação não tenta contornar autenticação; use uma fonte pública/API "
        "autorizada ou uma integração oficial compatível com sua conta."
    )


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    """Produz lotes estáveis para não exceder o limite da URL da API."""
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _to_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if pd.notna(numeric) else None


def _safe_ratio(numerator: Any, denominator: Any) -> float | None:
    numerator = _to_float(numerator)
    denominator = _to_float(denominator)
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _brapi_get(
    session: requests.Session,
    base_url: str,
    endpoint: str,
    params: dict[str, Any],
    token: str,
    timeout: float,
    retries: int = 3,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    for attempt in range(retries + 1):
        try:
            response = session.get(url, params=params, headers=headers, timeout=timeout)
            transient_status = response.status_code == 429 or response.status_code >= 500
            if transient_status and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            if not response.ok:
                try:
                    detail = response.json().get("message", "")
                except ValueError:
                    detail = ""
                suffix = f" — {detail}" if detail else ""
                raise RuntimeError(
                    f"brapi respondeu HTTP {response.status_code} em {endpoint}{suffix}"
                )
            response.raise_for_status()
            payload = response.json()
            break
        except requests.RequestException as exc:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Falha ao consultar brapi ({endpoint}): {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"brapi retornou JSON inválido em {endpoint}.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"brapi retornou formato inesperado em {endpoint}.")
    return payload


def _brapi_list_stocks(
    session: requests.Session,
    base_url: str,
    token: str,
    timeout: float,
    page_size: int,
) -> list[dict[str, Any]]:
    """Lista todo o universo de ações B3, paginando a cotação básica."""
    stocks: list[dict[str, Any]] = []
    page = 1

    while True:
        payload = _brapi_get(
            session,
            base_url,
            "/quote/list",
            {
                "type": "stock",
                "subType": "stock",
                "limit": page_size,
                "page": page,
            },
            token,
            timeout,
        )
        page_stocks = payload.get("stocks", [])
        if not isinstance(page_stocks, list):
            raise RuntimeError("brapi não retornou a lista de ações esperada.")
        stocks.extend(item for item in page_stocks if isinstance(item, dict))

        if not payload.get("hasNextPage", False):
            break
        page += 1

    unique: dict[str, dict[str, Any]] = {}
    for item in stocks:
        ticker = str(item.get("stock", "")).strip().upper()
        if ticker:
            unique[ticker] = item
    return list(unique.values())


def _brapi_data_by_ticker(
    session: requests.Session,
    base_url: str,
    endpoint: str,
    tickers: list[str],
    token: str,
    timeout: float,
    batch_size: int,
    extra_params: dict[str, Any] | None = None,
    workers: int = 1,
) -> dict[str, Any]:
    """Consulta endpoints multi-ticker e indexa ``results[].data`` pelo ticker."""
    def fetch(batch: list[str]) -> list[dict[str, Any]]:
        params = {"symbols": ",".join(batch)}
        if extra_params:
            params.update(extra_params)
        # requests.Session não é thread-safe. Cada tarefa abre sua própria
        # sessão, mas a paginação inicial continua usando a sessão recebida.
        with requests.Session() as worker_session:
            payload = _brapi_get(
                worker_session, base_url, endpoint, params, token, timeout,
            )
        rows = payload.get("results", [])
        if not isinstance(rows, list):
            raise RuntimeError(f"brapi não retornou results em {endpoint}.")
        return [row for row in rows if isinstance(row, dict)]

    result: dict[str, Any] = {}
    batches = list(_chunks(tickers, batch_size))
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(fetch, batch) for batch in batches]
            rows_by_batch = (future.result() for future in as_completed(futures))
            rows_iter = (row for rows in rows_by_batch for row in rows)
            for row in rows_iter:
                ticker = str(row.get("symbol") or row.get("requestedSymbol") or "").strip().upper()
                if ticker:
                    result[ticker] = row.get("data", {})
        return result

    for batch in batches:
        for row in fetch(batch):
            ticker = str(row.get("symbol") or row.get("requestedSymbol") or "").strip().upper()
            if ticker:
                result[ticker] = row.get("data", {})
    return result


def _latest_statement(data: Any) -> dict[str, Any]:
    if not isinstance(data, list):
        return {}
    rows = [row for row in data if isinstance(row, dict)]
    return max(rows, key=lambda row: str(row.get("endDate", "")), default={})


def _ttm_statement_value(data: Any, field: str) -> float | None:
    """Soma os quatro trimestres mais recentes, como a documentação recomenda."""
    if not isinstance(data, list):
        return None
    rows = sorted(
        (row for row in data if isinstance(row, dict)),
        key=lambda row: str(row.get("endDate", "")),
        reverse=True,
    )[:4]
    values = [_to_float(row.get(field)) for row in rows]
    values = [value for value in values if value is not None]
    return sum(values) if len(values) == 4 else None


def _mean_history_volume(data: Any) -> float | None:
    if not isinstance(data, dict):
        return None
    history = data.get("historicalDataPrice", [])
    if not isinstance(history, list):
        return None
    volumes = [
        _to_float(row.get("volume"))
        for row in history
        if isinstance(row, dict)
    ]
    volumes = [value for value in volumes if value is not None]
    return sum(volumes) / len(volumes) if volumes else None


def _build_brapi_acoes_frame(
    listings: list[dict[str, Any]],
    statistics: dict[str, Any],
    financial_data: dict[str, Any],
    income_statements: dict[str, Any],
    balance_sheets: dict[str, Any],
    price_history: dict[str, Any],
) -> pd.DataFrame:
    """Converte o contrato da brapi para o contrato histórico do screener."""
    rows: list[dict[str, Any]] = []
    data_preco = datetime.now().strftime("%d/%m/%Y")

    for listing in listings:
        ticker = str(listing.get("stock", "")).strip().upper()
        if not ticker:
            continue
        stats = statistics.get(ticker, {}) if isinstance(statistics.get(ticker), dict) else {}
        financial = financial_data.get(ticker, {}) if isinstance(financial_data.get(ticker), dict) else {}
        income = income_statements.get(ticker, [])
        balance = _latest_statement(balance_sheets.get(ticker, []))

        assets = _to_float(balance.get("totalAssets"))
        liabilities = _to_float(balance.get("totalLiab"))
        equity = _to_float(balance.get("shareholdersEquity"))
        ebit_ttm = _ttm_statement_value(income, "ebit")
        nopat_ttm = _ttm_statement_value(income, "cleanNopat")
        enterprise_value = _to_float(stats.get("enterpriseValue"))
        total_debt = _to_float(financial.get("totalDebt"))
        total_cash = _to_float(financial.get("totalCash"))
        invested_capital = (
            equity + total_debt - total_cash
            if equity is not None and total_debt is not None and total_cash is not None
            else None
        )

        rows.append({
            "Ação": ticker,
            "Empresa": listing.get("name") or ticker,
            "Preço": _to_float(listing.get("close")),
            "Data Preço": data_preco,
            "Data Dem.Financ.": balance.get("endDate"),
            "Consolidação": "Consolidado",
            "ROInvC": _safe_ratio(nopat_ttm, invested_capital),
            "RPL": _to_float(financial.get("returnOnEquity")),
            "ROA": _to_float(financial.get("returnOnAssets")),
            "Margem Líquida": _to_float(financial.get("profitMargins")),
            "Margem Bruta": _to_float(financial.get("grossMargins")),
            "Margem EBIT": _to_float(financial.get("operatingMargins")),
            "Giro do Ativo Inicial": _safe_ratio(financial.get("totalRevenue"), assets),
            "Alavancagem Financeira": _safe_ratio(assets, equity),
            "Passivo/Patrimônio Líquido": _safe_ratio(liabilities, equity),
            "Preço/Lucro": _to_float(stats.get("trailingPE")),
            "Preço/VPA": _to_float(stats.get("priceToBook")),
            "Preço/Receita Líquida": _safe_ratio(
                listing.get("market_cap") or stats.get("marketCap"),
                financial.get("totalRevenue"),
            ),
            "Preço/EBIT": _safe_ratio(
                listing.get("market_cap") or stats.get("marketCap"), ebit_ttm
            ),
            "EV/EBIT": _safe_ratio(enterprise_value, ebit_ttm),
            "EV/EBITDA": _to_float(stats.get("enterpriseToEbitda")),
            "EV/Receita Líquida": _to_float(stats.get("enterpriseToRevenue")),
            "EV/FCF": _safe_ratio(enterprise_value, financial.get("freeCashflow")),
            "EV/FCO": _safe_ratio(enterprise_value, financial.get("operatingCashflow")),
            "EV/Ativo Total": _safe_ratio(enterprise_value, assets),
            "Dividend Yield": _to_float(stats.get("dividendYield") or stats.get("yield")),
            "Volume Diário Médio (3 meses)": _mean_history_volume(price_history.get(ticker)),
            "Market Cap Empresa": _to_float(listing.get("market_cap") or stats.get("marketCap")),
            "# Ações Total": _to_float(stats.get("sharesOutstanding")),
            # Bases para atualizar os múltiplos diariamente sem repetir a
            # coleta de demonstrações financeiras, que muda em ritmo trimestral.
            "Brapi VPA": _to_float(stats.get("bookValue")),
            "Brapi LPA": _to_float(stats.get("trailingEps")),
            "Brapi Dividendo Anual por Ação": _safe_ratio(
                (_to_float(stats.get("dividendYield") or stats.get("yield")) or 0)
                * (_to_float(listing.get("close")) or 0),
                1,
            ),
            "Brapi Dívida Líquida": _safe_ratio(
                enterprise_value - (_to_float(listing.get("market_cap") or stats.get("marketCap")) or 0)
                if enterprise_value is not None else None,
                1,
            ),
            "Brapi EBIT TTM": ebit_ttm,
            "Brapi EBITDA TTM": _to_float(financial.get("ebitda")),
            "Brapi Receita TTM": _to_float(financial.get("totalRevenue")),
            "Brapi Atualizado Em": datetime.now().isoformat(timespec="seconds"),
        })

    return pd.DataFrame(rows)


def _brapi_cache_is_fresh(df: pd.DataFrame, ttl_days: int) -> bool:
    if df.empty or "Brapi Atualizado Em" not in df.columns:
        return False
    updated_at = pd.to_datetime(df["Brapi Atualizado Em"], errors="coerce", utc=True).max()
    if pd.isna(updated_at):
        return False
    age = pd.Timestamp.now(tz="UTC") - updated_at
    return age <= pd.Timedelta(days=ttl_days)


def _refresh_brapi_market_fields(
    cached: pd.DataFrame,
    listings: list[dict[str, Any]],
) -> pd.DataFrame:
    """Atualiza cotações e múltiplos que variam com o preço usando o cache."""
    market = pd.DataFrame(listings).rename(columns={
        "stock": "Ação", "name": "Empresa", "close": "_preco_atual",
        "market_cap": "_market_cap_atual",
    })
    required = {"Ação", "_preco_atual", "_market_cap_atual"}
    if market.empty or not required.issubset(market.columns):
        raise RuntimeError("brapi não retornou preço e market cap para atualizar o cache.")

    market["Ação"] = market["Ação"].astype(str).str.strip().str.upper()
    market = market.drop_duplicates(subset=["Ação"], keep="last")
    updated = cached.copy()
    updated["Ação"] = updated["Ação"].astype(str).str.strip().str.upper()
    updated = updated.merge(
        market[["Ação", "Empresa", "_preco_atual", "_market_cap_atual"]],
        on="Ação", how="inner", suffixes=("", "_mercado"),
    )

    for column in ("_preco_atual", "_market_cap_atual"):
        updated[column] = pd.to_numeric(updated[column], errors="coerce")
    updated["Preço"] = updated["_preco_atual"]
    updated["Market Cap Empresa"] = updated["_market_cap_atual"]
    if "Empresa_mercado" in updated.columns:
        updated["Empresa"] = updated["Empresa_mercado"].fillna(updated["Empresa"])
        updated = updated.drop(columns=["Empresa_mercado"])

    def ratio(num_col: str, den_col: str) -> pd.Series:
        numerator = pd.to_numeric(updated[num_col], errors="coerce")
        denominator = pd.to_numeric(updated[den_col], errors="coerce")
        return numerator.div(denominator.mask(denominator == 0))

    updated["Preço/VPA"] = ratio("Preço", "Brapi VPA")
    updated["Preço/Lucro"] = ratio("Preço", "Brapi LPA")
    updated["Dividend Yield"] = ratio("Brapi Dividendo Anual por Ação", "Preço")
    enterprise_value = (
        pd.to_numeric(updated["Market Cap Empresa"], errors="coerce")
        + pd.to_numeric(updated["Brapi Dívida Líquida"], errors="coerce")
    )
    updated["EV/EBIT"] = enterprise_value.div(
        pd.to_numeric(updated["Brapi EBIT TTM"], errors="coerce").replace(0, pd.NA)
    )
    updated["EV/EBITDA"] = enterprise_value.div(
        pd.to_numeric(updated["Brapi EBITDA TTM"], errors="coerce").replace(0, pd.NA)
    )
    updated["EV/Receita Líquida"] = enterprise_value.div(
        pd.to_numeric(updated["Brapi Receita TTM"], errors="coerce").replace(0, pd.NA)
    )
    updated["Preço/Receita Líquida"] = ratio("Market Cap Empresa", "Brapi Receita TTM")
    return updated.drop(columns=["_preco_atual", "_market_cap_atual"])


def _read_brapi_cache(cache_file: str) -> pd.DataFrame:
    path = Path(cache_file)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        logger.warning("Não foi possível ler cache brapi %s: %s", path, exc)
        return pd.DataFrame()


def _write_brapi_cache(df: pd.DataFrame, cache_file: str) -> None:
    path = Path(cache_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def validate_brapi_access(cfg: dict) -> str:
    """Valida credencial/plano antes de qualquer escrita do pipeline."""
    token = str(cfg.get("brapi_token", "")).strip()
    if not token:
        raise RuntimeError(
            "BRAPI_TOKEN não configurado. Crie o token na brapi e armazene-o "
            "como secret/variável de ambiente antes de executar o screener."
        )

    base_url = str(cfg.get("brapi_base_url", "https://brapi.dev/api"))
    timeout = float(cfg.get("brapi_timeout", 30))
    with requests.Session() as session:
        payload = _brapi_get(
            session, base_url, "/v2/user/usage", {}, token, timeout,
        )
    usage = payload.get("usage", {})
    plan = str(usage.get("planName", "")).strip().lower()
    if plan != "pro":
        raise PermissionError(
            f"O plano {plan or 'desconhecido'} da brapi não libera todos os "
            "dados fundamentalistas usados pelo screener. O plano Pro é necessário "
            "para P/L, P/VP, dividend yield, margens, ROA, balanço e DRE."
        )
    return plan


def scrape_acoes_brapi(cfg: dict) -> pd.DataFrame:
    """Coleta ações e fundamentos pela API autorizada da brapi.

    O token é deliberadamente lido de ``BRAPI_TOKEN`` via ``config.yaml``;
    ele não é salvo no repositório nem incluído em logs.
    """
    plan = validate_brapi_access(cfg)
    token = str(cfg.get("brapi_token", "")).strip()

    base_url = str(cfg.get("brapi_base_url", "https://brapi.dev/api"))
    timeout = float(cfg.get("brapi_timeout", 30))
    batch_size = int(cfg.get("brapi_batch_size", 50))
    page_size = int(cfg.get("brapi_page_size", 100))
    workers = int(cfg.get("brapi_workers", 1))
    ttl_days = int(cfg.get("brapi_fundamentals_ttl_days", 30))
    cache_file = str(cfg.get("brapi_cache_file", "data/lake/brapi_acoes_fundamentals.parquet"))
    if batch_size < 1 or page_size < 1 or workers < 1 or ttl_days < 1:
        raise ValueError("Configurações brapi devem ser positivas.")

    logger.info("Coletando ações via brapi (plano %s).", plan)
    with requests.Session() as session:
        listings = _brapi_list_stocks(session, base_url, token, timeout, page_size)
        tickers = [str(item.get("stock", "")).strip().upper() for item in listings]
        tickers = [ticker for ticker in tickers if ticker]
        if not tickers:
            raise RuntimeError("brapi não retornou nenhuma ação listada.")

        cached = _read_brapi_cache(cache_file)
        if _brapi_cache_is_fresh(cached, ttl_days):
            logger.info("Usando fundamentos brapi em cache (%s).", cache_file)
            df = _refresh_brapi_market_fields(cached, listings)
        else:
            logger.info("Atualizando fundamentos brapi; cache ausente ou expirado.")
            statistics = _brapi_data_by_ticker(
                session, base_url, "/v2/stocks/statistics", tickers,
                token, timeout, batch_size, workers=workers,
            )
            financial_data = _brapi_data_by_ticker(
                session, base_url, "/v2/stocks/financial-data", tickers,
                token, timeout, batch_size, workers=workers,
            )
            income_statements = _brapi_data_by_ticker(
                session, base_url, "/v2/stocks/income-statement", tickers,
                token, timeout, batch_size, {"period": "quarterly"}, workers,
            )
            balance_sheets = _brapi_data_by_ticker(
                session, base_url, "/v2/stocks/balance-sheet", tickers,
                token, timeout, batch_size, {"period": "quarterly"}, workers,
            )
            price_history = _brapi_data_by_ticker(
                session, base_url, "/v2/stocks/historical", tickers,
                token, timeout, batch_size, {"range": "3mo", "interval": "1d"}, workers,
            )
            df = _build_brapi_acoes_frame(
                listings, statistics, financial_data, income_statements,
                balance_sheets, price_history,
            )
            _write_brapi_cache(df, cache_file)

    df = clean_acoes_raw(df)
    logger.info("Ações brapi coletadas: %d linhas x %d colunas", *df.shape)
    return df


def scrape_fundsexplorer(cfg: dict) -> pd.DataFrame:
    url = cfg["url"]
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    logger.info(f"Iniciando scraping: {url}")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    wait = WebDriverWait(driver, cfg["wait_timeout"])

    try:
        _load_page(driver, url, cfg.get("page_load_timeout", cfg["wait_timeout"]))
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "tbody")))
        time.sleep(cfg["sleep_after_load"])

        # fecha banner de cookies se existir
        try:
            btn = driver.find_element(By.ID, cfg["cookie_button_id"])
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
            logger.debug("Banner de cookies fechado.")
        except Exception:
            pass

        # clica em "Selecionar Todos" para exibir todas as colunas
        try:
            select_all = wait.until(EC.presence_of_element_located(
                (By.ID, "colunas-ranking__todos")
            ))
            driver.execute_script("arguments[0].click();", select_all)
            time.sleep(2)
            logger.info("Todas as colunas selecionadas.")
        except Exception as e:
            logger.warning(f"Não foi possível clicar em 'Selecionar Todos': {e}")

        # aguarda tabela recarregar com todas as colunas
        time.sleep(3)

        # Ler cada célula por Selenium transforma 550 linhas em milhares de
        # idas e voltas ao Chrome e pode deixar a execução presa. O DOM já tem
        # a tabela completa, então extraímos tudo em uma única chamada.
        table_data = driver.execute_script(
            """
            return {
              headers: Array.from(document.querySelectorAll('thead tr th'))
                .map(cell => (cell.innerText || '').trim()),
              rows: Array.from(document.querySelectorAll('tbody tr'))
                .map(row => Array.from(row.querySelectorAll('td'))
                  .map(cell => (cell.innerText || '').trim()))
                .filter(row => row.some(cell => cell))
            };
            """
        )
        headers = table_data.get("headers", []) if isinstance(table_data, dict) else []
        rows = table_data.get("rows", []) if isinstance(table_data, dict) else []

        if not rows:
            raise RuntimeError("Nenhuma linha extraída da tabela.")

        # garante alinhamento entre headers e colunas
        max_cols = max(len(r) for r in rows)
        if len(headers) < max_cols:
            headers += [f"col_{i}" for i in range(len(headers), max_cols)]

        df = pd.DataFrame(rows, columns=headers[:max_cols])
        logger.info(f"Scraping concluído: {df.shape[0]} linhas x {df.shape[1]} colunas")
        logger.info(f"Colunas coletadas: {df.columns.tolist()}")
        return df

    except Exception as e:
        logger.error(f"Erro no scraping: {e}")
        raise

    finally:
        driver.quit()


def clean_acoes_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Remove rodapé/legenda que o Investsite inclui no Excel exportado."""
    if df.empty:
        return df

    df = df.dropna(how="all").copy()
    n_antes = len(df)

    for col in ("Ação", "Empresa"):
        if col in df.columns:
            mask_legenda = df[col].astype(str).str.strip().str.lower().eq("legenda")
            df = df[~mask_legenda]

    if "Preço" in df.columns:
        preco_num = pd.to_numeric(df["Preço"], errors="coerce")
        invalid = df["Preço"].notna() & preco_num.isna()
        df = df[~invalid]

    n_removidas = n_antes - len(df)
    if n_removidas:
        logger.info(
            f"Ações após limpeza de rodapé: {n_antes} → {len(df)} "
            f"({n_removidas} linhas removidas)"
        )

    return df.reset_index(drop=True)


def _wait_for_excel_download(
    download_dir: str,
    started_at: float,
    timeout: float,
) -> str:
    """Espera o Excel iniciado nesta execução terminar de baixar.

    Um ``sleep(8)`` fixo fazia a coleta falhar em conexões lentas e também
    podia reutilizar um arquivo de uma execução anterior. Consideramos apenas
    arquivos criados depois do clique e aguardamos o fim dos ``.crdownload``.
    """
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        files = [
            os.path.join(download_dir, filename)
            for filename in os.listdir(download_dir)
            if filename.lower().endswith((".xls", ".xlsx"))
            and os.path.getmtime(os.path.join(download_dir, filename)) >= started_at - 1
        ]
        pending = any(
            filename.lower().endswith(".crdownload")
            and os.path.getmtime(os.path.join(download_dir, filename)) >= started_at - 1
            for filename in os.listdir(download_dir)
        )

        if files and not pending:
            return max(files, key=os.path.getmtime)

        time.sleep(0.5)

    raise FileNotFoundError(
        "Arquivo Excel de ações não encontrado ou não finalizou o download "
        f"em {timeout:.0f}s."
    )


def scrape_acoes_investsite(cfg: dict) -> pd.DataFrame:
    """Coleta ranking de ações do Investsite via Selenium (download de Excel).

    Args:
        cfg: dicionário com chaves 'acoes_url', 'wait_timeout', 'download_dir'

    Returns:
        DataFrame bruto com os dados de ações.
    """
    url = cfg.get("acoes_url", "https://www.investsite.com.br/seleciona_acoes.php")
    download_dir = os.path.abspath(cfg.get("download_dir", "data/input/acoes_download"))
    os.makedirs(download_dir, exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    options.add_experimental_option("prefs", prefs)

    logger.info(f"Iniciando scraping de ações: {url}")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    wait = WebDriverWait(driver, cfg["wait_timeout"])

    try:
        _load_page(driver, url, cfg.get("page_load_timeout", cfg["wait_timeout"]))
        time.sleep(3)
        _raise_if_investsite_login_required(driver)

        # clica em "Procurar Ações"
        btn_procurar = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(),'Procurar Ações')]")
            )
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", btn_procurar)
        time.sleep(0.5)
        btn_procurar.click()
        logger.info("Botão 'Procurar Ações' clicado.")

        # clica em "Baixar Arquivo Excel"
        btn_excel = wait.until(
            EC.element_to_be_clickable((By.XPATH,
                "//input[contains(@value,'Baixar Arquivo Excel')] | "
                "//button[contains(text(),'Baixar Arquivo Excel')]"
            ))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", btn_excel)
        time.sleep(0.5)
        download_started_at = time.time()
        btn_excel.click()
        logger.info("Botão 'Baixar Arquivo Excel' clicado.")

        latest = _wait_for_excel_download(
            download_dir=download_dir,
            started_at=download_started_at,
            timeout=cfg.get("download_timeout", cfg["wait_timeout"]),
        )
        logger.info(f"Arquivo baixado: {latest}")

        df = pd.read_excel(latest, sheet_name=0, header=2)
        logger.info(f"Ações brutas: {df.shape[0]} linhas x {df.shape[1]} colunas")
        df = clean_acoes_raw(df)
        return df

    except Exception as e:
        logger.error(f"Erro no scraping de ações: {e}")
        raise

    finally:
        driver.quit()

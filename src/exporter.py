"""exporter.py — Exporta os dados do screener para JSON consumido pelo dashboard web."""

import json
import logging
import os

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _safe(val):
    if val is None:
        return None
    if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return round(float(val), 4)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    return val


def _df_to_records(df: pd.DataFrame, cols: list) -> list:
    if df is None or df.empty:
        return []

    existing = [c for c in cols if c in df.columns]
    records = []

    for _, row in df[existing].iterrows():
        records.append({col: _safe(row[col]) for col in existing})

    return records


def _serie_to_records(df_serie) -> list:
    if df_serie is None or (hasattr(df_serie, "empty") and df_serie.empty):
        return []

    out = []
    for _, r in df_serie.iterrows():
        out.append({
            "data": pd.to_datetime(r["data"]).strftime("%Y-%m-%d"),
            "valor": _safe(r["valor"]),
        })
    return out


def _base100_records(df_serie) -> list:
    """Converte uma série de valores absolutos em base 100.

    Uso principal: IBOV/IFIX/IMOB. Isso evita comparar índice em pontos
    contra carteira em retorno percentual/proxy. Tudo passa a ser crescimento.
    """
    records = _serie_to_records(df_serie)
    clean = [r for r in records if r.get("valor") is not None]

    if not clean:
        return []

    first = float(clean[0]["valor"])
    if first == 0:
        return []

    return [
        {
            "data": r["data"],
            "valor": round(float(r["valor"]) / first * 100, 4),
        }
        for r in clean
    ]


def _calc_tendencia(val_hoje, val_anterior, threshold_pct=2.0) -> str:
    if val_hoje is None or val_anterior is None:
        return "neutro"

    try:
        variacao = (float(val_hoje) - float(val_anterior)) / abs(float(val_anterior)) * 100
        if variacao > threshold_pct:
            return "subindo"
        if variacao < -threshold_pct:
            return "caindo"
        return "estavel"
    except (ZeroDivisionError, TypeError, ValueError):
        return "neutro"


def _load_previous_json(data_dir: str, data_hoje: str) -> dict:
    try:
        index_path = os.path.join(data_dir, "index.json")
        if not os.path.exists(index_path):
            return {}

        with open(index_path, encoding="utf-8") as f:
            datas = json.load(f)

        datas_anteriores = [d for d in sorted(datas, reverse=True) if d < data_hoje]
        if not datas_anteriores:
            return {}

        prev_path = os.path.join(data_dir, f"{datas_anteriores[0]}.json")
        if not os.path.exists(prev_path):
            return {}

        with open(prev_path, encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        logger.warning(f"Nao foi possivel carregar JSON anterior: {e}")
        return {}


def _add_tendencias_fiis(records: list, prev_data: dict) -> list:
    prev_fiis = {r["FUNDOS"]: r for r in prev_data.get("fiis", []) if "FUNDOS" in r}
    cols_tendencia = ["DIVIDEND YIELD", "P/VP", "LIQUIDEZ DIÁRIA (R$)", "VOLATILIDADE"]

    for rec in records:
        ticker = rec.get("FUNDOS")
        prev = prev_fiis.get(ticker, {})
        rec["tendencias"] = {
            col: _calc_tendencia(rec.get(col), prev.get(col))
            for col in cols_tendencia
            if col in rec
        }

    return records


def _add_tendencias_acoes(records: list, prev_data: dict) -> list:
    prev_acoes = {r["Ação"]: r for r in prev_data.get("acoes", []) if "Ação" in r}
    cols_tendencia = ["Dividend Yield", "Preço/VPA", "ROA", "Margem Líquida"]

    for rec in records:
        ticker = rec.get("Ação")
        prev = prev_acoes.get(ticker, {})
        rec["tendencias"] = {
            col: _calc_tendencia(rec.get(col), prev.get(col))
            for col in cols_tendencia
            if col in rec
        }

    return records


def _mean_numeric(df: pd.DataFrame, col: str):
    if df is None or df.empty or col not in df.columns:
        return None
    serie = pd.to_numeric(df[col], errors="coerce").dropna()
    if serie.empty:
        return None
    return _safe(serie.mean())


def _calc_kpis(top_fiis, top_acoes, fii_universe, acoes_universe) -> dict:
    """Calcula KPIs do dashboard e suas bases comparativas.

    Convenção:
    - *_carteira: média dos ativos selecionados no Top 20 do dia.
    - *_mercado: média do universo completo analisado no mesmo dia.

    Isso permite que o frontend mostre, abaixo do valor principal, se a
    carteira está acima ou abaixo da média geral do mercado filtrado.
    """
    kpis = {}

    kpis["dy_medio_fiis_carteira"] = _mean_numeric(top_fiis, "DIVIDEND YIELD")
    kpis["dy_medio_fiis_mercado"] = _mean_numeric(fii_universe, "DIVIDEND YIELD")
    kpis["pvp_medio_fiis_carteira"] = _mean_numeric(top_fiis, "P/VP")
    kpis["pvp_medio_fiis_mercado"] = _mean_numeric(fii_universe, "P/VP")
    kpis["score_medio_fiis_carteira"] = _mean_numeric(top_fiis, "Score")
    kpis["score_medio_fiis_mercado"] = _mean_numeric(fii_universe, "Score")

    kpis["dy_medio_acoes_carteira"] = _mean_numeric(top_acoes, "Dividend Yield")
    kpis["dy_medio_acoes_mercado"] = _mean_numeric(acoes_universe, "Dividend Yield")
    kpis["score_medio_acoes_carteira"] = _mean_numeric(top_acoes, "Score")
    kpis["score_medio_acoes_mercado"] = _mean_numeric(acoes_universe, "Score")

    kpis["total_fiis_universo"] = int(len(fii_universe)) if fii_universe is not None else 0
    kpis["total_acoes_universo"] = int(len(acoes_universe)) if acoes_universe is not None else 0

    return kpis


def _base100_records_from_date(df_serie, start_date: pd.Timestamp | None = None) -> list:
    """Converte série absoluta em base 100 a partir de uma data de início.

    Se a carteira começa em uma data posterior ao último ponto disponível do
    benchmark, devolve pelo menos um ponto em 100 na data de início. Isso evita
    gráfico em branco no primeiro dia de histórico real.
    """
    records = _serie_to_records(df_serie)
    clean_all = []

    for r in records:
        if r.get("valor") is None:
            continue
        try:
            data = pd.to_datetime(r["data"]).normalize()
            valor = float(r["valor"])
        except (TypeError, ValueError):
            continue
        clean_all.append({"data_ts": data, "data": data.strftime("%Y-%m-%d"), "valor": valor})

    clean_all = sorted(clean_all, key=lambda x: x["data_ts"])
    if not clean_all:
        return []

    if start_date is None:
        clean = clean_all
        base_value = float(clean[0]["valor"])
        base_date = clean[0]["data_ts"]
    else:
        start_date = pd.Timestamp(start_date).normalize()
        anteriores = [r for r in clean_all if r["data_ts"] <= start_date]
        posteriores = [r for r in clean_all if r["data_ts"] >= start_date]

        if anteriores:
            base_value = float(anteriores[-1]["valor"])
        elif posteriores:
            base_value = float(posteriores[0]["valor"])
        else:
            return []

        base_date = start_date
        clean = [r for r in clean_all if r["data_ts"] >= start_date]

        # Se ainda não existe fechamento de benchmark após a data da carteira,
        # mantém o ponto inicial em 100. O próximo pregão preencherá a sequência.
        if not clean:
            return [{"data": start_date.strftime("%Y-%m-%d"), "valor": 100.0}]

        # Garante que todas as séries comparativas nasçam exatamente na mesma data.
        if clean[0]["data_ts"] != start_date:
            clean = [{"data_ts": start_date, "data": start_date.strftime("%Y-%m-%d"), "valor": base_value}] + clean

    if base_value == 0:
        return []

    out = []
    for r in clean:
        out.append({
            "data": r["data"],
            "valor": round(float(r["valor"]) / base_value * 100, 4),
        })

    if start_date is not None and (not out or out[0]["data"] != base_date.strftime("%Y-%m-%d")):
        out.insert(0, {"data": base_date.strftime("%Y-%m-%d"), "valor": 100.0})

    return out


def _normalize_ticker_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def _load_parquet_safe(path: str) -> pd.DataFrame:
    try:
        if not os.path.exists(path):
            return pd.DataFrame()
        return pd.read_parquet(path)
    except Exception as e:
        logger.warning(f"Nao foi possivel carregar parquet {path}: {e}")
        return pd.DataFrame()


def _build_portfolio_base100_from_history(
    tipo: str,
    carteira_path: str,
    historico_path: str,
    ticker_col: str,
    price_col: str,
) -> list:
    """Monta série real da carteira Top 20 em base 100 usando histórico salvo.

    A linha da carteira começa somente na primeira data real registrada em
    data/backtest/carteiras_historicas.parquet. Para cada intervalo entre
    snapshots, mede o retorno equal-weight dos tickers escolhidos no início
    do período usando os preços do universo histórico no dia seguinte.
    """
    carteiras = _load_parquet_safe(carteira_path)
    historico = _load_parquet_safe(historico_path)

    required_carteira = {"Data_Carteira", "Tipo", "Ticker"}
    required_hist = {"Data_Execucao", ticker_col, price_col}

    if carteiras.empty or historico.empty:
        return []
    if not required_carteira.issubset(carteiras.columns):
        logger.warning(f"Carteiras sem colunas esperadas para {tipo}: {required_carteira}")
        return []
    if not required_hist.issubset(historico.columns):
        logger.warning(f"Historico sem colunas esperadas para {tipo}: {required_hist}")
        return []

    c = carteiras.copy()
    h = historico.copy()

    c = c[c["Tipo"].astype(str).str.upper().eq(tipo.upper())].copy()
    if c.empty:
        return []

    c["Data_Carteira"] = pd.to_datetime(c["Data_Carteira"], errors="coerce").dt.normalize()
    c["Ticker_norm"] = _normalize_ticker_series(c["Ticker"])
    c = c.dropna(subset=["Data_Carteira"])

    h["Data_Execucao"] = pd.to_datetime(h["Data_Execucao"], errors="coerce").dt.normalize()
    h["Ticker_norm"] = _normalize_ticker_series(h[ticker_col])
    h["Preco_norm"] = pd.to_numeric(h[price_col], errors="coerce")
    h = h.dropna(subset=["Data_Execucao", "Preco_norm"])

    dates = sorted(c["Data_Carteira"].dropna().unique())
    dates = [pd.Timestamp(d).normalize() for d in dates]
    if not dates:
        return []

    valor = 100.0
    out = [{"data": dates[0].strftime("%Y-%m-%d"), "valor": round(valor, 4)}]

    price_matrix = h.drop_duplicates(["Data_Execucao", "Ticker_norm"]).pivot(
        index="Data_Execucao",
        columns="Ticker_norm",
        values="Preco_norm",
    )

    for i in range(len(dates) - 1):
        inicio = dates[i]
        fim = dates[i + 1]

        tickers = (
            c.loc[c["Data_Carteira"].eq(inicio), "Ticker_norm"]
            .dropna()
            .unique()
            .tolist()
        )
        if not tickers or inicio not in price_matrix.index or fim not in price_matrix.index:
            out.append({"data": fim.strftime("%Y-%m-%d"), "valor": round(valor, 4)})
            continue

        p0 = price_matrix.loc[inicio].reindex(tickers)
        p1 = price_matrix.loc[fim].reindex(tickers)
        valid = p0.notna() & p1.notna() & (p0 != 0)

        if valid.sum() == 0:
            out.append({"data": fim.strftime("%Y-%m-%d"), "valor": round(valor, 4)})
            continue

        retornos = (p1[valid] / p0[valid]) - 1.0
        retorno_periodo = float(retornos.mean())
        valor *= (1.0 + retorno_periodo)
        out.append({"data": fim.strftime("%Y-%m-%d"), "valor": round(valor, 4)})

    return out


def _series_start_date(series: list) -> pd.Timestamp | None:
    if not series:
        return None
    try:
        return pd.to_datetime(series[0]["data"]).normalize()
    except Exception:
        return None


def _benchmark_dict_from_start(benchmarks: dict, names: list[str], start_date: pd.Timestamp | None) -> dict:
    out = {}
    for name in names:
        serie = benchmarks.get(name)
        out[name] = _base100_records_from_date(serie, start_date)
    return out


def _calc_carteira_vs_benchmarks(
    top_fiis: pd.DataFrame,
    top_acoes: pd.DataFrame,
    benchmarks: dict,
    data_hoje: str,
) -> dict:
    """Monta séries comparativas em base 100 tecnicamente consistentes.

    As carteiras Top 20 só começam quando existe histórico real salvo em
    data/backtest/carteiras_historicas.parquet. Os benchmarks de comparação
    são rebaseados para 100 na mesma data inicial da carteira.

    - FIIs: Top 20 FIIs vs IFIX, IMOB e CDI
    - Ações: Top 20 Ações vs IBOV, IPCA e CDI
    """
    resultado = {}

    # Séries longas para gráficos de mercado, independentes das carteiras.
    for name in ["IBOV", "IFIX", "IMOB", "CDI", "IPCA"]:
        if name in benchmarks:
            resultado[f"{name.lower()}_base100"] = _base100_records_from_date(benchmarks.get(name))

    carteira_path = os.path.join("data", "backtest", "carteiras_historicas.parquet")
    fii_hist_path = os.path.join("data", "ml", "historico_fiis.parquet")
    acoes_hist_path = os.path.join("data", "ml", "historico_acoes.parquet")

    fiis_series = _build_portfolio_base100_from_history(
        tipo="FII",
        carteira_path=carteira_path,
        historico_path=fii_hist_path,
        ticker_col="FUNDOS",
        price_col="PREÇO ATUAL (R$)",
    )
    acoes_series = _build_portfolio_base100_from_history(
        tipo="ACAO",
        carteira_path=carteira_path,
        historico_path=acoes_hist_path,
        ticker_col="Ação",
        price_col="Preço",
    )

    # Fallback honesto para o primeiro dia: se o parquet ainda não tiver sido
    # lido por qualquer motivo, cria apenas o ponto inicial em 100. Não inventa
    # performance; só evita um gráfico vazio.
    if not fiis_series and top_fiis is not None and not top_fiis.empty:
        fiis_series = [{"data": data_hoje, "valor": 100.0}]
    if not acoes_series and top_acoes is not None and not top_acoes.empty:
        acoes_series = [{"data": data_hoje, "valor": 100.0}]

    resultado["carteira_fiis_base100"] = fiis_series
    resultado["carteira_acoes_base100"] = acoes_series

    fiis_start = _series_start_date(fiis_series)
    acoes_start = _series_start_date(acoes_series)

    resultado["comparativo_fiis"] = {
        "inicio": fiis_start.strftime("%Y-%m-%d") if fiis_start is not None else None,
        "carteira": fiis_series,
        "benchmarks": _benchmark_dict_from_start(benchmarks, ["IFIX", "IMOB", "CDI"], fiis_start),
    }
    resultado["comparativo_acoes"] = {
        "inicio": acoes_start.strftime("%Y-%m-%d") if acoes_start is not None else None,
        "carteira": acoes_series,
        "benchmarks": _benchmark_dict_from_start(benchmarks, ["IBOV", "IPCA", "CDI"], acoes_start),
    }

    return resultado


def export_dashboard_json(
    output_dir: str,
    data_hoje: str,
    top_fiis: pd.DataFrame,
    top_acoes: pd.DataFrame,
    market_data: dict,
    fii_universe: pd.DataFrame = None,
    acoes_universe: pd.DataFrame = None,
    benchmarks: dict = None,
    fii_scores: pd.Series = None,
    acoes_scores: pd.Series = None,
    backtest: dict = None,
):
    os.makedirs(output_dir, exist_ok=True)

    fii_universe = fii_universe if fii_universe is not None else pd.DataFrame()
    acoes_universe = acoes_universe if acoes_universe is not None else pd.DataFrame()
    benchmarks = benchmarks or {}

    prev_data = _load_previous_json(output_dir, data_hoje)

    fii_cols = [
        "FUNDOS", "SETOR", "PREÇO ATUAL (R$)", "DIVIDEND YIELD", "P/VP",
        "LIQUIDEZ DIÁRIA (R$)", "PATRIMÔNIO LÍQUIDO", "VOLATILIDADE",
        "VPA", "ÚLTIMO DIVIDENDO", "NUM. COTISTAS",
    ]

    acoes_cols = [
        "Ação", "Empresa", "Preço", "Preço/VPA", "Preço/Lucro",
        "Dividend Yield", "ROA", "Margem Líquida", "Market Cap Empresa",
        "Market CapEmpresa", "EV/EBITDA", "RPL", "EV/EBIT",
    ]

    fiis_records = _df_to_records(top_fiis, fii_cols)
    acoes_records = _df_to_records(top_acoes, acoes_cols)

    if fii_scores is not None and top_fiis is not None and not top_fiis.empty:
        for i, rec in enumerate(fiis_records):
            try:
                rec["score"] = _safe(fii_scores.iloc[i])
            except (IndexError, KeyError):
                rec["score"] = None

    if acoes_scores is not None and top_acoes is not None and not top_acoes.empty:
        for i, rec in enumerate(acoes_records):
            try:
                rec["score"] = _safe(acoes_scores.iloc[i])
            except (IndexError, KeyError):
                rec["score"] = None

    fiis_records = _add_tendencias_fiis(fiis_records, prev_data)
    acoes_records = _add_tendencias_acoes(acoes_records, prev_data)

    kpis = _calc_kpis(top_fiis, top_acoes, fii_universe, acoes_universe)

    from src.benchmark import benchmarks_to_json

    benchmarks_json = benchmarks_to_json(benchmarks)
    carteira_vs = _calc_carteira_vs_benchmarks(top_fiis, top_acoes, benchmarks, data_hoje)

    payload = {
        "data": data_hoje,
        "fiis": fiis_records,
        "acoes": acoes_records,
        "indicadores": {
            "cambio": market_data.get("cambio", {}),
            "ipca_12m": _serie_to_records(market_data.get("ipca_12m")),
            "selic": _serie_to_records(market_data.get("selic")),
            "igpm": _serie_to_records(market_data.get("igpm")),
        },
        "benchmarks": benchmarks_json,
        "carteira_vs": carteira_vs,
        "backtest": backtest or {"disponivel": False},
        "kpis": kpis,
        "resumo": {
            "total_fiis": len(top_fiis) if top_fiis is not None else 0,
            "total_acoes": len(top_acoes) if top_acoes is not None else 0,
            "dy_medio_fiis": _safe(top_fiis["DIVIDEND YIELD"].mean())
            if top_fiis is not None and not top_fiis.empty and "DIVIDEND YIELD" in top_fiis.columns else None,
            "pvp_medio_fiis": _safe(top_fiis["P/VP"].mean())
            if top_fiis is not None and not top_fiis.empty and "P/VP" in top_fiis.columns else None,
        },
    }

    file_path = os.path.join(output_dir, f"{data_hoje}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"JSON do dashboard salvo: {file_path}")

    index_path = os.path.join(output_dir, "index.json")
    datas = []
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            datas = json.load(f)

    if data_hoje not in datas:
        datas.append(data_hoje)

    datas = sorted(set(datas), reverse=True)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(datas, f, ensure_ascii=False, indent=2)

    logger.info(f"Indice atualizado: {len(datas)} datas disponíveis.")

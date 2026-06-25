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


def _calc_kpis(top_fiis, top_acoes, fii_universe, acoes_universe) -> dict:
    kpis = {}

    if top_fiis is not None and not top_fiis.empty:
        if "DIVIDEND YIELD" in top_fiis.columns:
            kpis["dy_medio_fiis_carteira"] = _safe(top_fiis["DIVIDEND YIELD"].mean())
        if "P/VP" in top_fiis.columns:
            kpis["pvp_medio_fiis"] = _safe(top_fiis["P/VP"].mean())

    if fii_universe is not None and not fii_universe.empty:
        if "DIVIDEND YIELD" in fii_universe.columns:
            kpis["dy_medio_fiis_mercado"] = _safe(fii_universe["DIVIDEND YIELD"].dropna().mean())
        kpis["total_fiis_universo"] = int(len(fii_universe))
    else:
        kpis["total_fiis_universo"] = 0

    if top_acoes is not None and not top_acoes.empty:
        if "Dividend Yield" in top_acoes.columns:
            kpis["dy_medio_acoes_carteira"] = _safe(top_acoes["Dividend Yield"].mean())

    if acoes_universe is not None and not acoes_universe.empty:
        if "Dividend Yield" in acoes_universe.columns:
            kpis["dy_medio_acoes_mercado"] = _safe(acoes_universe["Dividend Yield"].dropna().mean())
        kpis["total_acoes_universo"] = int(len(acoes_universe))
    else:
        kpis["total_acoes_universo"] = 0

    return kpis


def _calc_carteira_vs_benchmarks(
    top_fiis: pd.DataFrame,
    top_acoes: pd.DataFrame,
    benchmarks: dict,
    data_hoje: str,
) -> dict:
    """Monta séries comparativas em base 100.

    Importante: esta função NÃO mistura IBOV/IFIX em pontos com carteira em %.
    Tudo que sai daqui já está na mesma escala: crescimento desde a primeira data.

    A carteira ainda usa DY médio anualizado como proxy enquanto não houver histórico
    suficiente de preço por ativo. O proxy é representado como base 100 também.
    """
    resultado = {}

    ibov = benchmarks.get("IBOV")
    ifix = benchmarks.get("IFIX")

    resultado["ibov_base100"] = _base100_records(ibov)
    resultado["ifix_base100"] = _base100_records(ifix)

    benchmark_base = ibov if ibov is not None and not ibov.empty else ifix
    if benchmark_base is None or benchmark_base.empty:
        return resultado

    base_data = pd.to_datetime(benchmark_base["data"].min()).normalize()
    hoje = pd.to_datetime(data_hoje).normalize()
    total_dias = max((hoje - base_data).days, 1)

    if top_fiis is not None and not top_fiis.empty and "DIVIDEND YIELD" in top_fiis.columns:
        dy_anual = float(top_fiis["DIVIDEND YIELD"].dropna().mean()) * 12
        retorno_carteira = dy_anual * (total_dias / 365)
        resultado["carteira_fiis_base100"] = [
            {"data": base_data.strftime("%Y-%m-%d"), "valor": 100.0},
            {"data": data_hoje, "valor": round(100 * (1 + retorno_carteira), 4)},
        ]

    if top_acoes is not None and not top_acoes.empty and "Dividend Yield" in top_acoes.columns:
        dy_anual = float(top_acoes["Dividend Yield"].dropna().mean()) * 12
        retorno_carteira = dy_anual * (total_dias / 365)
        resultado["carteira_acoes_base100"] = [
            {"data": base_data.strftime("%Y-%m-%d"), "valor": 100.0},
            {"data": data_hoje, "valor": round(100 * (1 + retorno_carteira), 4)},
        ]

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

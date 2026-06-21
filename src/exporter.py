import json
import logging
import os
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def _df_to_records(df: pd.DataFrame, cols: list) -> list:
    """Converte um DataFrame em lista de dicts, mantendo só as colunas pedidas
    e tratando NaN/tipos numpy para serem serializáveis em JSON."""
    if df.empty:
        return []
    existing_cols = [c for c in cols if c in df.columns]
    subset = df[existing_cols].copy()

    records = []
    for _, row in subset.iterrows():
        record = {}
        for col in existing_cols:
            val = row[col]
            if pd.isna(val):
                record[col] = None
            elif isinstance(val, (np.integer,)):
                record[col] = int(val)
            elif isinstance(val, (np.floating,)):
                record[col] = float(val)
            else:
                record[col] = str(val)
        records.append(record)
    return records


def _serie_to_records(df_serie: pd.DataFrame) -> list:
    """Converte uma série temporal (data, valor) em lista de pontos para gráfico."""
    if df_serie is None or df_serie.empty:
        return []
    out = []
    for _, r in df_serie.iterrows():
        out.append({
            "data": r["data"].strftime("%Y-%m-%d"),
            "valor": float(r["valor"]) if pd.notna(r["valor"]) else None,
        })
    return out


def export_dashboard_json(
    output_dir: str,
    data_hoje: str,
    top_fiis: pd.DataFrame,
    top_acoes: pd.DataFrame,
    market_data: dict,
):
    """Gera o JSON resumido consumido pelo dashboard web (docs/data/YYYY-MM-DD.json).

    Args:
        output_dir: pasta onde salvar o JSON (ex: docs/data)
        data_hoje: data no formato YYYY-MM-DD
        top_fiis: DataFrame do Top N FIIs
        top_acoes: DataFrame do Top N Ações
        market_data: dict retornado por get_market_indicators()
    """
    os.makedirs(output_dir, exist_ok=True)

    fii_cols = [
        "FUNDOS", "SETOR", "PREÇO ATUAL (R$)", "DIVIDEND YIELD", "P/VP",
        "LIQUIDEZ DIÁRIA (R$)", "PATRIMÔNIO LÍQUIDO", "VOLATILIDADE",
    ]
    acoes_cols = [
        "Ação", "Empresa", "Preço", "Preço/VPA", "Preço/Lucro",
        "Dividend Yield", "ROA", "Margem Líquida", "Market Cap Empresa",
    ]

    payload = {
        "data": data_hoje,
        "fiis": _df_to_records(top_fiis, fii_cols),
        "acoes": _df_to_records(top_acoes, acoes_cols),
        "indicadores": {
            "cambio": market_data.get("cambio", {}),
            "ipca_12m": _serie_to_records(market_data.get("ipca_12m")),
            "selic": _serie_to_records(market_data.get("selic")),
            "igpm": _serie_to_records(market_data.get("igpm")),
        },
        "resumo": {
            "total_fiis": len(top_fiis),
            "total_acoes": len(top_acoes),
            "dy_medio_fiis": float(top_fiis["DIVIDEND YIELD"].mean()) if not top_fiis.empty and "DIVIDEND YIELD" in top_fiis.columns else None,
            "pvp_medio_fiis": float(top_fiis["P/VP"].mean()) if not top_fiis.empty and "P/VP" in top_fiis.columns else None,
        },
    }

    # salva o snapshot do dia
    file_path = os.path.join(output_dir, f"{data_hoje}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"JSON do dashboard salvo: {file_path}")

    # atualiza o índice de datas disponíveis
    index_path = os.path.join(output_dir, "index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            datas = json.load(f)
    else:
        datas = []

    if data_hoje not in datas:
        datas.append(data_hoje)
    datas = sorted(set(datas), reverse=True)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(datas, f, ensure_ascii=False, indent=2)
    logger.info(f"Índice de datas atualizado: {len(datas)} datas disponíveis.")

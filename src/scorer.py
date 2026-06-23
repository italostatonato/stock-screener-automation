"""
scorer.py

Calcula um escore composto (0-100) para FIIs e Ações com base na posição
de cada indicador dentro do universo do dia (ranking percentílico).

Lógica:
- Para cada indicador, calcula o percentil do ativo dentro do universo filtrado
- Indicadores "maior é melhor" → percentil direto
- Indicadores "menor é melhor" → percentil invertido (100 - percentil)
- Score final = média ponderada dos percentis, normalizada para 0-100
"""

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Pesos por indicador (FIIs)
FII_WEIGHTS = {
    "DIVIDEND YIELD":       0.30,  # maior é melhor
    "P/VP":                 0.25,  # menor é melhor
    "LIQUIDEZ DIÁRIA (R$)": 0.20,  # maior é melhor
    "PATRIMÔNIO LÍQUIDO":   0.15,  # maior é melhor
    "VOLATILIDADE":         0.10,  # menor é melhor
}
FII_DIRECTION = {
    "DIVIDEND YIELD":       "max",
    "P/VP":                 "min",
    "LIQUIDEZ DIÁRIA (R$)": "max",
    "PATRIMÔNIO LÍQUIDO":   "max",
    "VOLATILIDADE":         "min",
}

# Pesos por indicador (Ações)
ACOES_WEIGHTS = {
    "Dividend Yield":  0.20,  # maior é melhor
    "Preço/VPA":       0.20,  # menor é melhor
    "Preço/Lucro":     0.15,  # menor é melhor
    "ROA":             0.15,  # maior é melhor
    "Margem Líquida":  0.15,  # maior é melhor
    "EV/EBITDA":       0.15,  # menor é melhor
}
ACOES_DIRECTION = {
    "Dividend Yield":  "max",
    "Preço/VPA":       "min",
    "Preço/Lucro":     "min",
    "ROA":             "max",
    "Margem Líquida":  "max",
    "EV/EBITDA":       "min",
}


def _percentil_score(series: pd.Series, direction: str) -> pd.Series:
    """Converte uma série numérica em percentil 0-100.
    direction='max' → maior valor = maior score
    direction='min' → menor valor = maior score
    """
    ranks = series.rank(pct=True, na_option="bottom") * 100
    if direction == "min":
        ranks = 100 - ranks
    return ranks.clip(0, 100)


def score_fiis(df: pd.DataFrame) -> pd.Series:
    """Calcula score composto 0-100 para cada FII no DataFrame.

    Args:
        df: DataFrame com todos os FIIs (universo completo, pós limpeza)

    Returns:
        pd.Series com o score de cada linha, mesmo índice que df
    """
    scores = pd.DataFrame(index=df.index)
    total_weight = 0.0

    for col, weight in FII_WEIGHTS.items():
        if col not in df.columns:
            logger.warning(f"Coluna {col} ausente — ignorada no score FII")
            continue
        direction = FII_DIRECTION[col]
        scores[col] = _percentil_score(df[col], direction) * weight
        total_weight += weight

    if total_weight == 0:
        return pd.Series(0.0, index=df.index)

    composite = scores.sum(axis=1) / total_weight
    composite = composite.clip(0, 100).round(1)
    logger.info(f"Score FII calculado: média={composite.mean():.1f}, max={composite.max():.1f}, min={composite.min():.1f}")
    return composite


def score_acoes(df: pd.DataFrame) -> pd.Series:
    """Calcula score composto 0-100 para cada Ação no DataFrame.

    Args:
        df: DataFrame com todas as ações (universo completo, pós limpeza)

    Returns:
        pd.Series com o score de cada linha, mesmo índice que df
    """
    scores = pd.DataFrame(index=df.index)
    total_weight = 0.0

    for col, weight in ACOES_WEIGHTS.items():
        if col not in df.columns:
            logger.warning(f"Coluna {col} ausente — ignorada no score Ações")
            continue
        direction = ACOES_DIRECTION[col]
        scores[col] = _percentil_score(df[col], direction) * weight
        total_weight += weight

    if total_weight == 0:
        return pd.Series(0.0, index=df.index)

    composite = scores.sum(axis=1) / total_weight
    composite = composite.clip(0, 100).round(1)
    logger.info(f"Score Ações calculado: média={composite.mean():.1f}, max={composite.max():.1f}, min={composite.min():.1f}")
    return composite


def score_breakdown_fii(row: pd.Series, universe_df: pd.DataFrame) -> dict:
    """Retorna o breakdown do score por indicador para um FII específico."""
    breakdown = {}
    for col, weight in FII_WEIGHTS.items():
        if col not in universe_df.columns or pd.isna(row.get(col)):
            breakdown[col] = {"valor": None, "percentil": None, "peso": weight}
            continue
        direction = FII_DIRECTION[col]
        pct = _percentil_score(universe_df[col], direction).loc[row.name] if row.name in universe_df.index else None
        breakdown[col] = {
            "valor": float(row[col]) if pd.notna(row.get(col)) else None,
            "percentil": round(float(pct), 1) if pct is not None else None,
            "peso": weight,
            "direcao": direction,
        }
    return breakdown


def score_breakdown_acao(row: pd.Series, universe_df: pd.DataFrame) -> dict:
    """Retorna o breakdown do score por indicador para uma Ação específica."""
    breakdown = {}
    for col, weight in ACOES_WEIGHTS.items():
        if col not in universe_df.columns or pd.isna(row.get(col)):
            breakdown[col] = {"valor": None, "percentil": None, "peso": weight}
            continue
        direction = ACOES_DIRECTION[col]
        pct = _percentil_score(universe_df[col], direction).loc[row.name] if row.name in universe_df.index else None
        breakdown[col] = {
            "valor": float(row[col]) if pd.notna(row.get(col)) else None,
            "percentil": round(float(pct), 1) if pct is not None else None,
            "peso": weight,
            "direcao": direction,
        }
    return breakdown

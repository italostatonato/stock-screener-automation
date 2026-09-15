"""Mantém a identidade do horizonte de cada previsão, inclusive no legado."""

import re

import pandas as pd


def prediction_horizons(frame: pd.DataFrame) -> pd.Series:
    result = pd.Series(pd.NA, index=frame.index, dtype="string")
    if "Horizonte" in frame:
        result = frame["Horizonte"].astype("string").str.strip().str.lower()
    evidence = {}
    for column in frame:
        match = re.fullmatch(r"retorno_(?:esperado|previsto_score_\w+)_(\d+d)", column)
        if match:
            horizon = match.group(1)
            present = pd.to_numeric(frame[column], errors="coerce").notna()
            evidence[horizon] = evidence.get(horizon, False) | present
    if evidence:
        candidates = pd.DataFrame(evidence, index=frame.index)
        unique = candidates.sum(axis=1).eq(1)
        inferred = candidates.idxmax(axis=1).where(unique)
        result = result.fillna(inferred)
    return result.fillna("indefinido")


def predictions_for_horizon(frame: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Scores supervisionados só são avaliados no horizonte que os gerou.

    Score Top independe do horizonte. Mantemos esse baseline das linhas legadas,
    mas sem reaproveitar scores de modelos de 30d como se fossem previsões de 7d.
    """
    out = frame.copy()
    matches = prediction_horizons(out).eq(f"{horizon}d")
    model_cols = [column for column in out if column.startswith("score_") and column != "score_top"]
    out.loc[~matches, model_cols] = float("nan")
    out["_horizon_match"] = matches
    keys = [column for column in ("Data_Execucao", "Tipo", "Ticker") if column in out]
    if keys:
        out = out.sort_values("_horizon_match", kind="stable").drop_duplicates(keys, keep="last")
    return out.drop(columns="_horizon_match")

import logging
import pandas as pd

logger = logging.getLogger(__name__)

_INVALID = {"N/A", "nan", "None", ""}


def _parse_percent(series: pd.Series) -> pd.Series:
    """'4,5%' → 0.045"""
    s = series.astype(str)
    s = s.str.replace("\u200b", "", regex=False)
    s = s.str.replace("%", "", regex=False)
    s = s.str.replace(".", "", regex=False)   # remove milhar
    s = s.str.replace(",", ".", regex=False)  # decimal
    s = s.str.strip()
    s = s.replace(list(_INVALID), None)
    return pd.to_numeric(s, errors="coerce") / 100


def _parse_money(series: pd.Series) -> pd.Series:
    """'R$ 1.234,56' → 1234.56"""
    s = series.astype(str)
    s = s.str.replace("\u200b", "", regex=False)
    s = s.str.replace("R$", "", regex=False)
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    s = s.str.strip()
    s = s.replace(list(_INVALID), None)
    return pd.to_numeric(s, errors="coerce")


def _parse_float(series: pd.Series) -> pd.Series:
    """'1,05' → 1.05"""
    s = series.astype(str)
    s = s.str.replace(",", ".", regex=False)
    s = s.str.strip()
    s = s.replace(list(_INVALID), None)
    return pd.to_numeric(s, errors="coerce")


def _parse_integer(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", "", regex=False)
    s = s.str.strip()
    s = s.replace(list(_INVALID), None)
    return pd.to_numeric(s, errors="coerce", downcast="integer")


def clean_and_normalize(df_raw: pd.DataFrame, col_cfg: dict) -> pd.DataFrame:
    df = df_raw.copy()
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    for col in col_cfg.get("percent", []):
        if col in df.columns:
            df[col] = _parse_percent(df_raw[col])
            logger.debug(f"Percentual: {col}")

    for col in col_cfg.get("money", []):
        if col in df.columns:
            df[col] = _parse_money(df_raw[col])
            logger.debug(f"Monetário: {col}")

    for col in col_cfg.get("integer", []):
        if col in df.columns:
            df[col] = _parse_integer(df_raw[col])
            logger.debug(f"Inteiro: {col}")

    # P/VP separado pois é float simples
    if "P/VP" in df.columns:
        df["P/VP"] = _parse_float(df_raw["P/VP"])

    logger.info("Limpeza e normalização concluídas.")
    return df
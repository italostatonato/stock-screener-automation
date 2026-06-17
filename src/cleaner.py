import logging
import pandas as pd

logger = logging.getLogger(__name__)

_INVALID = {"N/A", "nan", "None", ""}


def _parse_percent(series):
    s = series.astype(str)
    s = s.str.replace("​", "", regex=False)
    s = s.str.replace("%", "", regex=False)
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    s = s.str.strip()
    s = s.replace(list(_INVALID), None)
    return pd.to_numeric(s, errors="coerce") / 100


def _parse_money(series):
    s = series.astype(str)
    s = s.str.replace("​", "", regex=False)
    s = s.str.replace("R$", "", regex=False)
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    s = s.str.strip()
    s = s.replace(list(_INVALID), None)
    return pd.to_numeric(s, errors="coerce")


def _parse_float(series):
    s = series.astype(str)
    s = s.str.replace(",", ".", regex=False)
    s = s.str.strip()
    s = s.replace(list(_INVALID), None)
    return pd.to_numeric(s, errors="coerce")


def _parse_integer(series):
    s = series.astype(str)
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", "", regex=False)
    s = s.str.strip()
    s = s.replace(list(_INVALID), None)
    return pd.to_numeric(s, errors="coerce", downcast="integer")


def clean_and_normalize(df_raw, col_cfg):
    df = df_raw.copy()
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    for col in col_cfg.get("percent", []):
        if col in df.columns:
            df[col] = _parse_percent(df_raw[col])

    for col in col_cfg.get("money", []):
        if col in df.columns:
            df[col] = _parse_money(df_raw[col])

    for col in col_cfg.get("integer", []):
        if col in df.columns:
            df[col] = _parse_integer(df_raw[col])

    for col in col_cfg.get("float_simple", []):
        if col in df.columns:
            df[col] = _parse_money(df_raw[col])

    if "P/VP" in df.columns:
        df["P/VP"] = _parse_float(df_raw["P/VP"])

    logger.info("Limpeza concluida.")
    return df

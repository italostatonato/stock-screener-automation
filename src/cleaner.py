import logging
import pandas as pd

logger = logging.getLogger(__name__)

_INVALID = {"N/A", "nan", "None", ""}


def _to_numeric_series(series: pd.Series, remove_chars: list[str]) -> pd.Series:
    s = series.astype(str)
    for ch in remove_chars:
        s = s.str.replace(ch, "", regex=False)
    s = s.str.replace("\u200b", "", regex=False)  # zero-width space
    s = s.str.strip()
    s = s.replace(_INVALID, None)
    return pd.to_numeric(s, errors="coerce")


def clean_and_normalize(df_raw: pd.DataFrame, col_cfg: dict) -> pd.DataFrame:
    """Normaliza tipos de dado do DataFrame bruto.

    Args:
        df_raw: DataFrame saído do scraper (tudo string).
        col_cfg: dict com chaves 'percent', 'money', 'integer'.

    Returns:
        DataFrame com tipos corretos.
    """
    df = df_raw.copy()
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    # Percentuais: '4,5%' → 0.045
    for col in col_cfg.get("percent", []):
        if col in df.columns:
            df[col] = _to_numeric_series(df[col], ["%", ".", ","]) 
            # re-aplica vírgula→ponto na ordem certa
            s = df[col + "_raw"] if col + "_raw" in df.columns else df_raw[col].astype(str)
            s = s.str.replace("%", "", regex=False)
            s = s.str.replace("\u200b", "", regex=False)
            s = s.str.replace(".", "", regex=False)   # milhar
            s = s.str.replace(",", ".", regex=False)  # decimal
            s = s.replace(list(_INVALID), None)
            df[col] = pd.to_numeric(s, errors="coerce") / 100
            logger.debug(f"Coluna percentual processada: {col}")

    # Monetárias: 'R$ 1.234,56' → 1234.56
    for col in col_cfg.get("money", []):
        if col in df.columns:
            s = df_raw[col].astype(str)
            s = s.str.replace("R$", "", regex=False)
            s = s.str.replace("\u200b", "", regex=False)
            s = s.str.replace(".", "", regex=False)
            s = s.str.replace(",", ".", regex=False)
            s = s.replace(list(_INVALID), None)
            df[col] = pd.to_numeric(s, errors="coerce")
            logger.debug(f"Coluna monetária processada: {col}")

    # P/VP
    if "P/VP" in df.columns:
        s = df_raw["P/VP"].astype(str).str.replace(",", ".", regex=False)
        s = s.replace(list(_INVALID), None)
        df["P/VP"] = pd.to_numeric(s, errors="coerce")

    # Inteiros
    for col in col_cfg.get("integer", []):
        if col in df.columns:
            s = df_raw[col].astype(str).str.replace(".", "", regex=False).str.replace(",", "", regex=False)
            s = s.replace(list(_INVALID), None)
            df[col] = pd.to_numeric(s, errors="coerce", downcast="integer")

    logger.info("Limpeza e normalização concluídas.")
    return df
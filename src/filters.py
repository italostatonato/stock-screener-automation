import logging
import pandas as pd

logger = logging.getLogger(__name__)


def select_top_fiis(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    required_cols = ["P/VPA", "Dividend Yield", "Liquidez Diária (R$)", "Patrimônio Líquido", "Volatilidade"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas ausentes no DataFrame: {missing}")

    filt = (
        (df["P/VPA"] < cfg["pvp_max"]) &
        (df["Dividend Yield"] > cfg["dy_min"]) &
        (df["Liquidez Diária (R$)"] > cfg["liquidez_min"]) &
        (df["Patrimônio Líquido"] > cfg["patrimonio_min"]) &
        (df["Volatilidade"].fillna(999999) < cfg["volatilidade_max"])
    )

    result = df.loc[filt].copy()
    logger.info(f"Filtros aplicados: {len(df)} → {len(result)} FIIs")

    if result.empty:
        logger.warning("Nenhum FII passou pelos filtros. Considere relaxar os critérios no config.yaml.")
        return result

    result = result.sort_values(
        by=["Dividend Yield", "P/VPA", "Liquidez Diária (R$)"],
        ascending=[False, True, False]
    ).head(cfg["top_n"]).reset_index(drop=True)

    logger.info(f"Top {len(result)} FIIs selecionados.")
    return result
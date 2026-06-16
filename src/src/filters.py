import logging
import pandas as pd

logger = logging.getLogger(__name__)


def select_top_fiis(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Aplica filtros e retorna os Top N FIIs rankeados.

    Args:
        df: DataFrame limpo.
        cfg: dicionário com os parâmetros de filtro (pvp_max, dy_min, etc.)

    Returns:
        DataFrame com até cfg['top_n'] linhas.
    """
    required_cols = ["P/VP", "DIVIDEND YIELD", "LIQUIDEZ DIÁRIA (R$)", "PATRIMÔNIO LÍQUIDO", "VOLATILIDADE"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas ausentes no DataFrame: {missing}")

    filt = (
        (df["P/VP"] < cfg["pvp_max"]) &
        (df["DIVIDEND YIELD"] > cfg["dy_min"]) &
        (df["LIQUIDEZ DIÁRIA (R$)"] > cfg["liquidez_min"]) &
        (df["PATRIMÔNIO LÍQUIDO"] > cfg["patrimonio_min"]) &
        (df["VOLATILIDADE"].fillna(999) < cfg["volatilidade_max"])
    )

    result = df.loc[filt].copy()
    total_antes = len(df)
    total_depois = len(result)
    logger.info(f"Filtros aplicados: {total_antes} → {total_depois} FIIs")

    if result.empty:
        logger.warning("Nenhum FII passou pelos filtros. Considere relaxar os critérios no config.yaml.")
        return result

    result = result.sort_values(
        by=["DIVIDEND YIELD", "P/VP", "LIQUIDEZ DIÁRIA (R$)"],
        ascending=[False, True, False]
    ).head(cfg["top_n"]).reset_index(drop=True)

    logger.info(f"Top {len(result)} FIIs selecionados.")
    return result
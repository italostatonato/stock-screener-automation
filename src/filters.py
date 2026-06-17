import logging
import pandas as pd

logger = logging.getLogger(__name__)


def select_top_fiis(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    required_cols = ["P/VP", "DIVIDEND YIELD", "LIQUIDEZ DIÁRIA (R$)", "PATRIMÔNIO LÍQUIDO", "VOLATILIDADE"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas ausentes no DataFrame: {missing}")

    filt = (
        (df["P/VP"] < cfg["pvp_max"]) &
        (df["DIVIDEND YIELD"] > cfg["dy_min"]) &
        (df["LIQUIDEZ DIÁRIA (R$)"] > cfg["liquidez_min"]) &
        (df["PATRIMÔNIO LÍQUIDO"] > cfg["patrimonio_min"]) &
        (df["VOLATILIDADE"].fillna(999999) < cfg["volatilidade_max"])
    )

    result = df.loc[filt].copy()
    logger.info(f"Filtros aplicados: {len(df)} → {len(result)} FIIs")

    if result.empty:
        logger.warning("Nenhum FII passou pelos filtros. Considere relaxar os critérios no config.yaml.")
        return result

    result = result.sort_values(
        by=["DIVIDEND YIELD", "P/VP", "LIQUIDEZ DIÁRIA (R$)"],
        ascending=[False, True, False]
    ).head(cfg["top_n"]).reset_index(drop=True)

    logger.info(f"Top {len(result)} FIIs selecionados.")
    return result

def select_top_acoes(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Aplica filtros fundamentalistas e retorna Top N ações.

    Args:
        df: DataFrame bruto do Investsite (header na linha 2).
        cfg: dicionário com parâmetros de filtro de ações.
    """
    required_cols = [
        "Preço/VPA", "Preço/Lucro", "EV/EBIT", "EV/EBITDA",
        "Margem Líquida", "ROA", "RPL", "ROInvC",
        "Passivo/Patrimônio Líquido", "Alavancagem Financeira",
        "Dividend Yield", "Volume Diário Médio (3 meses)", "Market Cap Empresa"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logger.warning(f"Colunas ausentes em ações: {missing}")

    # limpeza básica
    result = df.copy()
    result = result.dropna(subset=["Ação", "Preço"])
    result = result.drop_duplicates(subset=["Empresa"], keep="first")

    acoes_cfg = cfg.get("acoes", {})

    filt = (
        (result["Preço/VPA"].between(0, acoes_cfg.get("pvpa_max", 5))) &
        (result["Preço/Lucro"] < acoes_cfg.get("pl_max", 15)) &
        (result["EV/EBIT"] < acoes_cfg.get("ev_ebit_max", 10)) &
        (result["EV/EBITDA"] < acoes_cfg.get("ev_ebitda_max", 8)) &
        (result["Margem Líquida"] > acoes_cfg.get("margem_min", 0.05)) &
        (result["ROA"] > acoes_cfg.get("roa_min", 0.03)) &
        (result["RPL"] > acoes_cfg.get("rpl_min", 0.10)) &
        (result["ROInvC"] > acoes_cfg.get("roinvc_min", 0.05)) &
        (result["Passivo/Patrimônio Líquido"] < acoes_cfg.get("passivo_pl_max", 1.5)) &
        (result["Alavancagem Financeira"] < acoes_cfg.get("alavancagem_max", 3)) &
        (result["Dividend Yield"] > acoes_cfg.get("dy_min", 0.04)) &
        (result["Volume Diário Médio (3 meses)"] > acoes_cfg.get("volume_min", 1_000_000)) &
        (result["Market Cap Empresa"] > acoes_cfg.get("market_cap_min", 500_000_000))
    )

    result = result.loc[filt].copy()
    logger.info(f"Filtros ações: {len(df)} → {len(result)} ações")

    if result.empty:
        logger.warning("Nenhuma ação passou pelos filtros. Considere relaxar os critérios no config.yaml.")
        return result

    result = result.sort_values(
        by=["Preço/VPA", "Dividend Yield"],
        ascending=[True, False]
    ).head(acoes_cfg.get("top_n", 20)).reset_index(drop=True)

    logger.info(f"Top {len(result)} ações selecionadas.")
    return result
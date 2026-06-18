import logging
import pandas as pd

logger = logging.getLogger(__name__)


def _log_quartis(df: pd.DataFrame, col: str, q: float, direcao: str):
    """Loga o valor de corte calculado para auditoria."""
    val = df[col].quantile(q)
    logger.info(f"  {col}: Q{int(q*100)} = {val:.4f} ({direcao})")
    return val


def select_top_fiis(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Recebe diretamente cfg["filters"].
    """

    required_cols = [
        "P/VP",
        "DIVIDEND YIELD",
        "LIQUIDEZ DIÁRIA (R$)",
        "PATRIMÔNIO LÍQUIDO",
        "VOLATILIDADE"
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas ausentes no DataFrame FII: {missing}")

    f = cfg

    # ── Camada 1: filtros fixos ──────────────────────────────────────────────
    base = df[
        (df["P/VP"].notna()) &
        (df["DIVIDEND YIELD"].notna()) &
        (df["LIQUIDEZ DIÁRIA (R$)"].notna()) &
        (df["PATRIMÔNIO LÍQUIDO"].notna()) &
        (df["VOLATILIDADE"].notna()) &
        (df["P/VP"] > 0) &
        (df["DIVIDEND YIELD"] > f["dy_min"]) &
        (df["LIQUIDEZ DIÁRIA (R$)"] > f["liquidez_min"]) &
        (df["PATRIMÔNIO LÍQUIDO"] > f["patrimonio_min"])
    ].copy()

    logger.info(f"FIIs após filtros fixos: {len(df)} → {len(base)}")

    if base.empty:
        logger.warning("Nenhum FII passou nos filtros fixos.")
        return base

    # ── Camada 2: quartis ────────────────────────────────────────────────────
    logger.info("Calculando quartis FIIs:")

    q_pvp = _log_quartis(base, "P/VP", 0.25, "≤ Q25 melhor")
    q_dy = _log_quartis(base, "DIVIDEND YIELD", 0.75, "≥ Q75 melhor")
    q_liquidez = _log_quartis(base, "LIQUIDEZ DIÁRIA (R$)", 0.75, "≥ Q75 melhor")
    q_patrimonio = _log_quartis(base, "PATRIMÔNIO LÍQUIDO", 0.75, "≥ Q75 melhor")
    q_vol = _log_quartis(base, "VOLATILIDADE", 0.75, "≤ Q75 melhor")

    result = base[
        (base["P/VP"] <= q_pvp) &
        (base["DIVIDEND YIELD"] >= q_dy) &
        (base["LIQUIDEZ DIÁRIA (R$)"] >= q_liquidez) &
        (base["PATRIMÔNIO LÍQUIDO"] >= q_patrimonio) &
        (base["VOLATILIDADE"] <= q_vol)
    ].copy()

    logger.info(f"FIIs após filtros por quartil: {len(base)} → {len(result)}")

    if result.empty:
        logger.warning(
            "Nenhum FII passou nos filtros por quartil — retornando Top N do universo base."
        )
        result = base.copy()

    result = result.sort_values(
        by=["DIVIDEND YIELD", "P/VP", "LIQUIDEZ DIÁRIA (R$)"],
        ascending=[False, True, False]
    ).head(f["top_n"]).reset_index(drop=True)

    logger.info(f"Top {len(result)} FIIs selecionados.")
    return result


def select_top_acoes(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Recebe diretamente cfg["filters"].
    """

    required_cols = [
        "Preço/VPA",
        "Preço/Lucro",
        "EV/EBIT",
        "EV/EBITDA",
        "Margem Líquida",
        "ROA",
        "RPL",
        "ROInvC",
        "Passivo/Patrimônio Líquido",
        "Alavancagem Financeira",
        "Dividend Yield",
        "Volume Diário Médio (3 meses)",
        "Market Cap Empresa"
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logger.warning(f"Colunas ausentes em ações: {missing}")

    result = df.copy()

    result = result.dropna(subset=["Ação", "Preço"])
    result = result.drop_duplicates(subset=["Empresa"], keep="first")

    a = cfg["acoes"]

    # ── Camada 1: filtros fixos ──────────────────────────────────────────────
    base = result[
        (result["Preço/VPA"].notna()) &
        (result["Margem Líquida"].notna()) &
        (result["Dividend Yield"].notna()) &
        (result["Volume Diário Médio (3 meses)"] > a["volume_min"]) &
        (result["Market Cap Empresa"] > a["market_cap_min"]) &
        (result["Margem Líquida"] > 0) &
        (result["ROA"] > 0) &
        (result["Dividend Yield"] > a["dy_min"])
    ].copy()

    logger.info(f"Ações após filtros fixos: {len(result)} → {len(base)}")

    if base.empty:
        logger.warning("Nenhuma ação passou nos filtros fixos.")
        return base

    # ── Camada 2: quartis ────────────────────────────────────────────────────
    logger.info("Calculando quartis Ações:")

    q_pvpa = _log_quartis(base, "Preço/VPA", 0.25, "≤ Q25 melhor")
    q_pl = _log_quartis(base, "Preço/Lucro", 0.25, "≤ Q25 melhor")
    q_ev_ebit = _log_quartis(base, "EV/EBIT", 0.25, "≤ Q25 melhor")
    q_ev_ebitda = _log_quartis(base, "EV/EBITDA", 0.25, "≤ Q25 melhor")
    q_margem = _log_quartis(base, "Margem Líquida", 0.75, "≥ Q75 melhor")
    q_roa = _log_quartis(base, "ROA", 0.75, "≥ Q75 melhor")
    q_rpl = _log_quartis(base, "RPL", 0.75, "≥ Q75 melhor")
    q_dy = _log_quartis(base, "Dividend Yield", 0.75, "≥ Q75 melhor")

    result = base[
        (base["Preço/VPA"] <= q_pvpa) &
        (base["Preço/Lucro"] <= q_pl) &
        (base["EV/EBIT"] <= q_ev_ebit) &
        (base["EV/EBITDA"] <= q_ev_ebitda) &
        (base["Margem Líquida"] >= q_margem) &
        (base["ROA"] >= q_roa) &
        (base["RPL"] >= q_rpl) &
        (base["Dividend Yield"] >= q_dy)
    ].copy()

    logger.info(f"Ações após filtros por quartil: {len(base)} → {len(result)}")

    if result.empty:
        logger.warning(
            "Nenhuma ação passou nos filtros por quartil — retornando Top N do universo base."
        )
        result = base.copy()

    result = result.sort_values(
        by=["Preço/VPA", "Dividend Yield"],
        ascending=[True, False]
    ).head(a["top_n"]).reset_index(drop=True)

    logger.info(f"Top {len(result)} ações selecionadas.")
    return result
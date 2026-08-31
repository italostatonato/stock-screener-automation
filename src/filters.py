import logging
import re
import unicodedata

import pandas as pd


logger = logging.getLogger(__name__)


def _normalized_company_name(value) -> str:
    """Normaliza razão/nome e remove apenas sufixos de classe do papel."""
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii").upper()
    tokens = re.sub(r"[^A-Z0-9]+", " ", text).split()
    share_class_tokens = {
        "ON", "PN", "PNA", "PNB", "PNC", "PND",
        "ORD", "PREF", "PREFERENCIAL", "UNIT", "UNT",
    }
    while tokens and tokens[-1] in share_class_tokens:
        tokens.pop()
    return " ".join(tokens)


def _company_key(row: pd.Series) -> str:
    """Identifica a companhia mesmo quando Empresa contém apenas o ticker."""
    ticker = str(row.get("Ação", "")).strip().upper()
    company = _normalized_company_name(row.get("Empresa"))
    ticker_normalized = _normalized_company_name(ticker)

    if company and company != ticker_normalized:
        return f"NOME:{company}"

    # Na B3, o número final representa a classe; o radical identifica o emissor.
    issuer = re.sub(r"(?:11|3|4|5|6|7|8)$", "", ticker)
    return f"TICKER:{issuer or ticker}"


def _build_status_column(
    df: pd.DataFrame,
    fixed_checks: list,
    rank_df: pd.DataFrame,
    id_col: str,
    duplicate_ids: set | None = None,
) -> pd.Series:
    """Explica a elegibilidade e a posição final de cada ativo."""
    status = pd.Series(index=df.index, dtype=object)

    for idx in df.index:
        row = df.loc[idx]
        motivo = None

        for label, cond_func in fixed_checks:
            if not cond_func(row):
                motivo = f"Eliminado no filtro fixo: {label}"
                break

        if motivo is None and duplicate_ids and row[id_col] in duplicate_ids:
            motivo = "Eliminado por duplicidade da empresa"

        if motivo is None:
            match = rank_df[rank_df[id_col] == row[id_col]]
            if not match.empty:
                motivo = f"Rank #{match.index[0] + 1}"
            else:
                motivo = "Aprovado (fora do Top N)"

        status.loc[idx] = motivo

    return status


def select_top_fiis(df: pd.DataFrame, cfg: dict):
    """Aplica pisos de elegibilidade e seleciona os FIIs pelo score."""
    required_cols = [
        "FUNDOS",
        "P/VP",
        "LIQUIDEZ DIÁRIA (R$)",
        "PATRIMÔNIO LÍQUIDO",
        "Score",
    ]
    # O backfill histórico antigo só possui o DY mensal. A execução atual
    # usa o DY médio de 12 meses escolhido para o novo score.
    dy_col = "DY (12M) MÉDIA" if "DY (12M) MÉDIA" in df.columns else "DIVIDEND YIELD"
    required_cols.append(dy_col)

    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Colunas ausentes no DataFrame FII: {missing}")

    f = cfg["filters"]
    base_full = df.copy()
    fixed_checks = [
        (
            "P/VP nulo ou não positivo",
            lambda row: pd.notna(row["P/VP"]) and row["P/VP"] > 0,
        ),
        (f"{dy_col} nulo", lambda row: pd.notna(row[dy_col])),
        (
            "LIQUIDEZ DIÁRIA nula",
            lambda row: pd.notna(row["LIQUIDEZ DIÁRIA (R$)"]),
        ),
        (
            "PATRIMÔNIO LÍQUIDO nulo",
            lambda row: pd.notna(row["PATRIMÔNIO LÍQUIDO"]),
        ),
        (
            f"DY médio <= {f['dy_min'] * 100:.2f}%",
            lambda row: row[dy_col] > f["dy_min"],
        ),
        (
            f"Liquidez <= {f['liquidez_min']:,.0f}",
            lambda row: row["LIQUIDEZ DIÁRIA (R$)"] > f["liquidez_min"],
        ),
        (
            f"Patrimônio <= {f['patrimonio_min']:,.0f}",
            lambda row: row["PATRIMÔNIO LÍQUIDO"] > f["patrimonio_min"],
        ),
    ]

    base = df[
        df.apply(lambda row: all(check(row) for _, check in fixed_checks), axis=1)
    ].copy()
    logger.info(f"FIIs após filtros fixos: {len(df)} → {len(base)}")

    if base.empty:
        logger.warning("Nenhum FII passou nos filtros fixos.")
        base_full["Status"] = "Eliminado no filtro fixo: dados insuficientes"
        return base, base_full

    # Os filtros acima definem somente elegibilidade. A classificação é feita
    # exclusivamente pelo score dos sete indicadores igualmente ponderados.
    result = base.copy()
    result["Score"] = pd.to_numeric(result["Score"], errors="coerce")
    result = (
        result.sort_values(
            by=["Score", "FUNDOS"],
            ascending=[False, True],
            na_position="last",
        )
        .head(f["top_n"])
        .reset_index(drop=True)
    )
    logger.info(f"Top {len(result)} FIIs selecionados.")

    base_full["Status"] = _build_status_column(
        base_full,
        fixed_checks,
        result,
        id_col="FUNDOS",
    )
    return result, base_full


def select_top_acoes(df: pd.DataFrame, cfg: dict):
    """Aplica pisos de elegibilidade e seleciona as ações pelo score."""
    required_cols = [
        "Ação",
        "Empresa",
        "Preço",
        "Preço/VPA",
        "EV/EBITDA",
        "Margem Líquida",
        "RPL",
        "ROInvC",
        "Dividend Yield",
        "Volume Diário Médio (3 meses)",
        "Market Cap Empresa",
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Colunas ausentes em ações: {missing}")

    base_full = df.copy()
    base_full = base_full.dropna(subset=["Ação", "Preço"])
    base_full = (
        base_full.drop_duplicates(subset=["Ação"], keep="first")
        .reset_index(drop=True)
    )

    a = cfg["filters"]["acoes"]
    fixed_checks = [
        (
            "Preço/VPA nulo ou não positivo",
            lambda row: pd.notna(row["Preço/VPA"]) and row["Preço/VPA"] > 0,
        ),
        (
            "EV/EBITDA nulo ou não positivo",
            lambda row: pd.notna(row["EV/EBITDA"]) and row["EV/EBITDA"] > 0,
        ),
        ("Dividend Yield nulo", lambda row: pd.notna(row["Dividend Yield"])),
        (
            f"Volume <= {a['volume_min']:,.0f}",
            lambda row: pd.notna(row["Volume Diário Médio (3 meses)"])
            and row["Volume Diário Médio (3 meses)"] > a["volume_min"],
        ),
        (
            f"Market Cap <= {a['market_cap_min']:,.0f}",
            lambda row: pd.notna(row["Market Cap Empresa"])
            and row["Market Cap Empresa"] > a["market_cap_min"],
        ),
        (
            f"DY <= {a['dy_min'] * 100:.2f}%",
            lambda row: row["Dividend Yield"] > a["dy_min"],
        ),
    ]

    base = base_full[
        base_full.apply(
            lambda row: all(check(row) for _, check in fixed_checks),
            axis=1,
        )
    ].copy()
    logger.info(f"Ações após filtros fixos: {len(base_full)} → {len(base)}")

    if base.empty:
        logger.warning("Nenhuma ação passou nos filtros fixos.")
        base_full["Status"] = "Eliminado no filtro fixo: dados insuficientes"
        return base, base_full

    # Os filtros acima definem somente elegibilidade. A classificação é feita
    # exclusivamente pelo score dos sete indicadores igualmente ponderados.
    result = base.copy()
    if "Score" in result.columns:
        result["Score"] = pd.to_numeric(result["Score"], errors="coerce")
        result = (
            result.sort_values(
                by=["Score", "Ação"],
                ascending=[False, True],
                na_position="last",
            )
        )
    else:
        # A função também é usada diretamente por testes e integrações
        # legadas que fornecem a base antes do cálculo do score.
        result = result.sort_values(by=["Ação"], ascending=[True])

    result["_Empresa_Chave"] = result.apply(_company_key, axis=1)
    deduplicated = result.drop_duplicates(subset=["_Empresa_Chave"], keep="first")
    duplicate_ids = set(result["Ação"]) - set(deduplicated["Ação"])
    if duplicate_ids:
        logger.info(
            "Ações removidas por duplicidade de empresa: %s",
            ", ".join(sorted(duplicate_ids)),
        )
    result = (
        deduplicated.head(a["top_n"])
        .drop(columns=["_Empresa_Chave"])
        .reset_index(drop=True)
    )

    base_full["Status"] = _build_status_column(
        base_full,
        fixed_checks,
        result,
        id_col="Ação",
        duplicate_ids=duplicate_ids,
    )
    return result, base_full

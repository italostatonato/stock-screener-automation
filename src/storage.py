import logging
import os
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


def save_snapshot(top_actions: pd.DataFrame, top_fiis: pd.DataFrame, snapshot_path: str):
    """Salva snapshot do dia com Acoes e FIIs em abas separadas."""
    os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    with pd.ExcelWriter(snapshot_path, engine="openpyxl") as writer:
        top_actions.to_excel(writer, sheet_name="Acoes BR", index=False)
        top_fiis.to_excel(writer, sheet_name="FII", index=False)
    logger.info(f"Snapshot salvo: {snapshot_path}")


def update_history(df_new: pd.DataFrame, hist_path: str, key_col: str):
    """Atualiza arquivo historico sem duplicar entradas.

    Args:
        df_new: DataFrame novo com coluna de data.
        hist_path: caminho do Excel historico.
        key_col: coluna que identifica o ativo (ex: 'FUNDOS' ou 'Acao').
    """
    os.makedirs(os.path.dirname(hist_path), exist_ok=True)

    if os.path.exists(hist_path):
        old = pd.read_excel(hist_path)
        combined = pd.concat([old, df_new], ignore_index=True)
        logger.info(f"Historico carregado: {len(old)} linhas antigas + {len(df_new)} novas")
    else:
        combined = df_new.copy()
        logger.info("Nenhum historico encontrado — criando novo arquivo.")

    # Detecta o nome da coluna de data (compatibilidade entre versoes)
    date_col = None
    for candidate in ["Data Preco", "Data Preco", "data_preco"]:
        if candidate in combined.columns:
            date_col = candidate
            break

    if date_col and key_col in combined.columns:
        combined.drop_duplicates(subset=[key_col, date_col], keep="last", inplace=True)
    elif key_col in combined.columns:
        combined.drop_duplicates(subset=[key_col], keep="last", inplace=True)

    combined.to_excel(hist_path, index=False)
    logger.info(f"Historico atualizado: {hist_path} ({len(combined)} linhas totais)")

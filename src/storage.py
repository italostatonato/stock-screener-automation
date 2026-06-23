import logging
import os
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


def save_snapshot(top_actions: pd.DataFrame, top_fiis: pd.DataFrame, snapshot_path: str):
    """Salva snapshot do dia com Ações e FIIs em abas separadas."""
    os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    with pd.ExcelWriter(snapshot_path, engine="openpyxl") as writer:
        top_actions.to_excel(writer, sheet_name="Ações BR", index=False)
        top_fiis.to_excel(writer, sheet_name="FII", index=False)
    logger.info(f"Snapshot salvo: {snapshot_path}")


def update_history(df_new: pd.DataFrame, hist_path: str, key_col: str):
    """Atualiza arquivo histórico sem duplicar entradas (mesmo fundo + mesma data).

    Args:
        df_new: DataFrame novo com coluna 'Data Preço'.
        hist_path: caminho do Excel histórico.
        key_col: coluna que identifica o ativo (ex: 'FUNDOS' ou 'Ação').
    """
    os.makedirs(os.path.dirname(hist_path), exist_ok=True)

    if os.path.exists(hist_path):
        old = pd.read_excel(hist_path)
        if "Data Preço" not in old.columns:
            old["Data Preço"] = pd.NA
        combined = pd.concat([old, df_new], ignore_index=True)
        logger.info(f"Histórico carregado: {len(old)} linhas antigas + {len(df_new)} novas")
    else:
        combined = df_new.copy()
        logger.info("Nenhum histórico encontrado — criando novo arquivo.")

    date_col = "Data Preço" if "Data Preço" in combined.columns else "Data Preco"
	combined.drop_duplicates(subset=[key_col, date_col], keep="last", inplace=True)
    combined.to_excel(hist_path, index=False)
    logger.info(f"Histórico atualizado: {hist_path} ({len(combined)} linhas totais)")
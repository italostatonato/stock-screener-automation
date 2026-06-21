import logging
import os
import sys
from datetime import datetime

import pandas as pd
import yaml

from src.scraper import scrape_fundsexplorer, scrape_acoes_investsite
from src.cleaner import clean_and_normalize
from src.filters import select_top_fiis, select_top_acoes
from src.storage import save_snapshot, update_history
from src.formatter import format_workbook
from src.market_data import get_market_indicators


def setup_logging(logs_dir: str):
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, f"{datetime.today().strftime('%Y-%m-%d')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    setup_logging(cfg["paths"]["logs_dir"])
    logger = logging.getLogger(__name__)
    logger.info("=== Screener iniciado ===")

    paths = cfg["paths"]
    data_hoje = datetime.today().strftime("%Y-%m-%d")

    # ── FIIs ──────────────────────────────────────────────────────────────────
    local_file = paths["local_input_file"]
    if os.path.exists(local_file):
        logger.info(f"Carregando arquivo local: {local_file}")
        df_raw = pd.read_excel(local_file)
    else:
        logger.info("Arquivo local não encontrado — coletando FIIs via Selenium.")
        df_raw = scrape_fundsexplorer(cfg["scraper"])

    df_clean = clean_and_normalize(df_raw, cfg["columns"])

    top_fiis, fii_base = select_top_fiis(df_clean, cfg)
    top_fiis["Data Preço"] = data_hoje

    update_history(
        top_fiis,
        os.path.join(paths["old_dir"], "Top_20_FII_BRL.xlsx"),
        key_col="FUNDOS"
    )

    # ── Ações ─────────────────────────────────────────────────────────────────
    logger.info("Coletando ações...")
    try:
        df_acoes_raw = scrape_acoes_investsite(cfg["scraper"])
        top_actions, acoes_base = select_top_acoes(df_acoes_raw, cfg)
        top_actions["Data Preço"] = data_hoje
        update_history(
            top_actions,
            os.path.join(paths["old_dir"], "Top_20_Acoes_BRL.xlsx"),
            key_col="Ação"
        )
    except Exception as e:
        logger.error(f"Falha no scraping de ações: {e} — continuando sem ações.")
        top_actions = pd.DataFrame()
        acoes_base = pd.DataFrame()

    # ── Indicadores de mercado ───────────────────────────────────────────────
    try:
        market_data = get_market_indicators()
    except Exception as e:
        logger.error(f"Falha ao coletar indicadores de mercado: {e}")
        market_data = {}

    # ── Snapshot ──────────────────────────────────────────────────────────────
    snapshot_path = os.path.join(
        paths["output_dir"], f"Top20_Ranking_{data_hoje}.xlsx"
    )
    save_snapshot(top_actions, top_fiis, snapshot_path)

    # ── Formatação completa (premissas, bases completas, gráficos, indicadores) ──
    format_workbook(
        snapshot_path=snapshot_path,
        cfg=cfg,
        data_hoje=data_hoje,
        n_fiis=len(top_fiis),
        n_acoes=len(top_actions),
        fii_base=fii_base,
        acoes_base=acoes_base,
        market_data=market_data,
    )

    logger.info("=== Screener finalizado com sucesso ===")


if __name__ == "__main__":
    main()
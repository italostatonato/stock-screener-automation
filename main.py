import logging
import os
import shutil
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
from src.exporter import export_dashboard_json
from src.scorer import score_fiis, score_acoes
from src.benchmark import get_benchmarks
from src.ml_storage import append_historical_data


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
        logger.info("Arquivo local nao encontrado — coletando FIIs via Selenium.")
        df_raw = scrape_fundsexplorer(cfg["scraper"])

    df_clean = clean_and_normalize(df_raw, cfg["columns"])

    logger.info("Calculando scores FIIs...")
    fii_scores_universe = score_fiis(df_clean)
    df_clean["Score"] = fii_scores_universe

    top_fiis, fii_base = select_top_fiis(df_clean, cfg)
    top_fiis["Data Preco"] = data_hoje

    fii_scores_top = (
        fii_scores_universe.reindex(top_fiis.index)
        if not top_fiis.empty
        else pd.Series(dtype=float)
    )

    update_history(
        top_fiis,
        os.path.join(paths["old_dir"], "Top_20_FII_BRL.xlsx"),
        key_col="FUNDOS",
    )

    # Historico ML (universo completo de FIIs)
    append_historical_data(
        df=df_clean,
        data_execucao=data_hoje,
        output_file=os.path.join(paths["old_dir"], "ml_historico_fiis.parquet"),
    )

    # ── Acoes ─────────────────────────────────────────────────────────────────
    logger.info("Coletando acoes...")
    try:
        df_acoes_raw = scrape_acoes_investsite(cfg["scraper"])

        logger.info("Calculando scores Acoes...")
        acoes_scores_universe = score_acoes(df_acoes_raw)
        df_acoes_raw["Score"] = acoes_scores_universe

        top_actions, acoes_base = select_top_acoes(df_acoes_raw, cfg)
        top_actions["Data Preco"] = data_hoje

        acoes_scores_top = (
            acoes_scores_universe.reindex(top_actions.index)
            if not top_actions.empty
            else pd.Series(dtype=float)
        )

        update_history(
            top_actions,
            os.path.join(paths["old_dir"], "Top_20_Acoes_BRL.xlsx"),
            key_col="Acao",
        )

        # Historico ML (universo completo de Acoes)
        append_historical_data(
            df=df_acoes_raw,
            data_execucao=data_hoje,
            output_file=os.path.join(paths["old_dir"], "ml_historico_acoes.parquet"),
        )

    except Exception as e:
        logger.error(f"Falha no scraping de acoes: {e} — continuando sem acoes.")
        top_actions = pd.DataFrame()
        acoes_base = pd.DataFrame()
        acoes_scores_top = pd.Series(dtype=float)
        df_acoes_raw = pd.DataFrame()

    # ── Indicadores de mercado ───────────────────────────────────────────────
    try:
        market_data = get_market_indicators()
    except Exception as e:
        logger.error(f"Falha ao coletar indicadores de mercado: {e}")
        market_data = {}

    # ── Benchmarks ────────────────────────────────────────────────────────────
    try:
        benchmarks = get_benchmarks(meses=13)
    except Exception as e:
        logger.error(f"Falha ao coletar benchmarks: {e}")
        benchmarks = {}

    # ── Snapshot Excel ────────────────────────────────────────────────────────
    snapshot_path = os.path.join(
        paths["output_dir"], f"Top20_Ranking_{data_hoje}.xlsx"
    )
    save_snapshot(top_actions, top_fiis, snapshot_path)

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

    # ── Exporta JSON para o dashboard web ───────────────────────────────────
    try:
        export_dashboard_json(
            output_dir=os.path.join("docs", "data"),
            data_hoje=data_hoje,
            top_fiis=top_fiis,
            top_acoes=top_actions,
            market_data=market_data,
            fii_universe=df_clean,
            acoes_universe=df_acoes_raw,
            benchmarks=benchmarks,
            fii_scores=fii_scores_top,
            acoes_scores=acoes_scores_top,
        )
    except Exception as e:
        logger.error(f"Falha ao exportar JSON do dashboard: {e}")

    # ── Copia para o OneDrive ───────────────────────────────────────────────
    onedrive_dir = paths.get("onedrive_output_dir")
    if onedrive_dir:
        try:
            os.makedirs(onedrive_dir, exist_ok=True)
            destino = os.path.join(onedrive_dir, os.path.basename(snapshot_path))
            shutil.copy2(snapshot_path, destino)
            logger.info(f"Copia salva no OneDrive: {destino}")
        except Exception as e:
            logger.error(f"Falha ao copiar para o OneDrive: {e}")

    logger.info("=== Screener finalizado com sucesso ===")


if __name__ == "__main__":
    main()

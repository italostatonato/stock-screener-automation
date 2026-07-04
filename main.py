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
from src.exporter import export_dashboard_json
from src.scorer import score_fiis, score_acoes
from src.benchmark import get_benchmarks
from src.backtest import run_backtest, save_portfolio_snapshot
from src.ml_storage import append_historical_data
from src.dataset_builder import build_all_datasets
from src.ml_models import run_ml_pipeline
from src.data_lake import save_lake_snapshot, run_data_quality_checks
from src.delivery import deliver_excel


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
    data_dir = paths.get("data_dir", "data")
    ml_dir = os.path.join(data_dir, "ml")
    backtest_dir = os.path.join(data_dir, "backtest")
    os.makedirs(ml_dir, exist_ok=True)
    os.makedirs(backtest_dir, exist_ok=True)

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

    # Histórico ML — universo completo de FIIs, com status de filtro quando disponível.
    try:
        fii_hist_source = fii_base if fii_base is not None and not fii_base.empty else df_clean
        append_historical_data(
            df=fii_hist_source,
            data_execucao=data_hoje,
            output_file=os.path.join(ml_dir, "historico_fiis.parquet"),
            subset_cols=["Data_Execucao", "FUNDOS"],
        )
    except Exception as e:
        logger.error(f"Falha ao salvar historico ML FIIs: {e}")

    # ── Ações ─────────────────────────────────────────────────────────────────
    logger.info("Coletando acoes...")
    top_actions = pd.DataFrame()
    acoes_base = pd.DataFrame()
    acoes_scores_top = pd.Series(dtype=float)
    df_acoes_raw = pd.DataFrame()

    try:
        df_acoes_raw = scrape_acoes_investsite(cfg["scraper"])
    except Exception as e:
        logger.error(f"Falha no scraping de acoes: {e} — continuando sem acoes.")
    else:
        try:
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
        except Exception as e:
            logger.error(f"Falha no processamento de acoes: {e} — continuando sem acoes processadas.")
            top_actions = pd.DataFrame()
            acoes_base = pd.DataFrame()
            acoes_scores_top = pd.Series(dtype=float)

    # Histórico ML — salva a base processada quando existir; se falhar, salva a base bruta.
    try:
        acoes_hist_source = acoes_base if acoes_base is not None and not acoes_base.empty else df_acoes_raw
        append_historical_data(
            df=acoes_hist_source,
            data_execucao=data_hoje,
            output_file=os.path.join(ml_dir, "historico_acoes.parquet"),
            subset_cols=["Data_Execucao", "Ação"],
        )
    except Exception as e:
        logger.error(f"Falha ao salvar historico ML Acoes: {e}")

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

    # ── Backtest legado FIIs ──────────────────────────────────────────────────
    try:
        backtest = run_backtest(
            os.path.join(paths["old_dir"], "Top_20_FII_BRL.xlsx"),
            data_fim=data_hoje,
        )
    except Exception as e:
        logger.error(f"Falha no backtest Top 20 FIIs: {e}")
        backtest = {"disponivel": False, "motivo": str(e)}

    # ── Histórico de carteiras para backtest futuro ───────────────────────────
    carteira_snapshot = pd.DataFrame()
    carteira_path = os.path.join(backtest_dir, "carteiras_historicas.parquet")
    try:
        save_portfolio_snapshot(
            top_fiis=top_fiis,
            top_acoes=top_actions,
            data_execucao=data_hoje,
            output_file=carteira_path,
        )

        if os.path.exists(carteira_path):
            carteira_all = pd.read_parquet(carteira_path)
            if "Data_Carteira" in carteira_all.columns:
                carteira_dates = pd.to_datetime(carteira_all["Data_Carteira"], errors="coerce").dt.strftime("%Y-%m-%d")
                carteira_snapshot = carteira_all[carteira_dates.eq(data_hoje)].copy()
    except Exception as e:
        logger.error(f"Falha ao salvar carteira historica de backtest: {e}")

    # ── Data lake incremental ────────────────────────────────────────────────
    # Mantém os parquets consolidados atuais por compatibilidade, mas também
    # salva snapshots diários separados. Isso prepara o projeto para crescer sem
    # depender de um único arquivo binário sendo regravado todos os dias.
    try:
        save_lake_snapshot(
            data_dir=data_dir,
            data_execucao=data_hoje,
            fii_universe=fii_hist_source if "fii_hist_source" in locals() else df_clean,
            acoes_universe=acoes_hist_source if "acoes_hist_source" in locals() else df_acoes_raw,
            top_fiis=top_fiis,
            top_acoes=top_actions,
            carteira_snapshot=carteira_snapshot,
        )
    except Exception as e:
        logger.error(f"Falha ao salvar snapshot incremental do data lake: {e}")

    # ── Datasets e modelos ML em modo sombra ─────────────────────────────────
    try:
        build_all_datasets(data_dir=data_dir, horizons=(7, 30, 60, 90))
    except Exception as e:
        logger.error(f"Falha ao gerar datasets ML: {e}")

    try:
        run_ml_pipeline(data_dir=data_dir, horizon=30)
    except Exception as e:
        logger.error(f"Falha ao executar pipeline ML sombra: {e}")

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
            backtest=backtest,
        )
    except Exception as e:
        logger.error(f"Falha ao exportar JSON do dashboard: {e}")

    # ── Checagens de qualidade e reconstrução robusta do índice ──────────────
    try:
        quality_report = run_data_quality_checks(
            data_dir=data_dir,
            dashboard_dir=os.path.join("docs", "data"),
        )
        logger.info(f"Data quality status: {quality_report.get('status')}")
    except Exception as e:
        logger.error(f"Falha nas checagens de qualidade: {e}")

    # ── Entrega segura do Excel final ───────────────────────────────────────
    # Fase 1: cópia local para pasta sincronizada do OneDrive.
    # Em GitHub Actions/Linux, paths Windows locais são ignorados com segurança.
    try:
        delivery_result = deliver_excel(
            snapshot_path=snapshot_path,
            cfg=cfg,
            data_execucao=data_hoje,
        )
        logger.info(
            "Entrega do Excel final: %s",
            delivery_result.to_dict(),
        )
    except Exception as e:
        logger.error(f"Falha inesperada na entrega do Excel final: {e}")

    logger.info("=== Screener finalizado com sucesso ===")


if __name__ == "__main__":
    main()

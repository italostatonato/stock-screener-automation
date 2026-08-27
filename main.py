import logging
import os
import sys
from datetime import datetime

import pandas as pd

from src.config import load_config
from src.scraper import (
    scrape_fundsexplorer,
    scrape_acoes,
)
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
from src.data_lake import (
    save_lake_snapshot,
    run_data_quality_checks,
    rebuild_legacy_tables_from_lake,
)
from src.delivery import deliver_excel


def setup_logging(logs_dir: str):
    os.makedirs(logs_dir, exist_ok=True)

    # No Windows o console pode iniciar em cp1252; os logs do projeto usam
    # acentos e símbolos matemáticos. Reconfigurar evita que um simples log
    # gere uma exceção e esconda o diagnóstico real da execução.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    log_file = os.path.join(
        logs_dir,
        f"{datetime.today().strftime('%Y-%m-%d')}.log",
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    cfg = load_config("config.yaml")

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

    # ── FIIs ──────────────────────────────────────────────────────────────

    local_file = paths["local_input_file"]

    if os.path.exists(local_file):
        logger.info(f"Carregando arquivo local: {local_file}")
        df_raw = pd.read_excel(local_file)
    else:
        logger.info(
            "Arquivo local nao encontrado — coletando FIIs via Selenium."
        )
        df_raw = scrape_fundsexplorer(cfg["scraper"])

    df_clean = clean_and_normalize(df_raw, cfg["columns"])

    logger.info("Calculando scores FIIs...")

    fii_scores_universe = score_fiis(df_clean)
    df_clean["Score"] = fii_scores_universe

    top_fiis, fii_base = select_top_fiis(df_clean, cfg)

    # Um Top FII vazio não é uma carteira válida. A checagem precisa acontecer
    # antes de qualquer escrita de histórico/snapshot para não deixar o lake
    # com uma execução parcial que o healthcheck só detectaria depois.
    if top_fiis is None or top_fiis.empty:
        raise RuntimeError(
            "select_top_fiis() retornou zero FIIs "
            f"(bruto={len(df_raw)}, normalizado={len(df_clean)}). "
            "Verifique a coleta e a normalização dos indicadores do FundsExplorer."
        )

    top_fiis["Data Preco"] = data_hoje

    # select_top_fiis() redefine o índice. Reindexar o score do universo pelo
    # índice do Top N associa scores de ativos diferentes; o score selecionado
    # já está presente no próprio DataFrame.
    fii_scores_top = (
        pd.to_numeric(top_fiis["Score"], errors="coerce")
        .reset_index(drop=True)
    )

    if fii_scores_top.notna().sum() == 0:
        raise RuntimeError("Top FIIs possui Score, mas todos os Scores são nulos.")

    update_history(
        top_fiis,
        os.path.join(paths["old_dir"], "Top_20_FII_BRL.xlsx"),
        key_col="FUNDOS",
    )

    # Histórico ML — universo completo de FIIs
    try:
        fii_hist_source = (
            fii_base
            if fii_base is not None and not fii_base.empty
            else df_clean
        )

        append_historical_data(
            df=fii_hist_source,
            data_execucao=data_hoje,
            output_file=os.path.join(
                ml_dir,
                "historico_fiis.parquet",
            ),
            subset_cols=["Data_Execucao", "FUNDOS"],
        )

    except Exception as e:
        logger.error(
            f"Falha ao salvar historico ML FIIs: {e}"
        )
    # ── Ações ─────────────────────────────────────────────────────────────
    logger.info("Coletando acoes...")

    df_acoes_raw = pd.DataFrame()
    top_actions = pd.DataFrame()
    acoes_base = pd.DataFrame()
    acoes_scores_top = pd.Series(dtype=float)

    # O pipeline de ações é obrigatório.
    # Se o scraping ou o processamento falhar, o workflow deve falhar
    # em vez de publicar uma carteira/dashboard sem ações.

    df_acoes_raw = scrape_acoes(cfg["scraper"])

    if df_acoes_raw is None or df_acoes_raw.empty:
        raise RuntimeError(
            "Scraping de ações retornou DataFrame vazio."
        )

    logger.info(
        "Ações coletadas: %d linhas, %d colunas",
        len(df_acoes_raw),
        len(df_acoes_raw.columns),
    )

    logger.info("Calculando scores Ações...")

    acoes_scores_universe = score_acoes(
        df_acoes_raw
    )

    df_acoes_raw["Score"] = acoes_scores_universe

    if df_acoes_raw["Score"].notna().sum() == 0:
        raise RuntimeError(
            "Score das ações ficou completamente vazio."
        )

    top_actions, acoes_base = select_top_acoes(
        df_acoes_raw,
        cfg,
    )

    if top_actions is None or top_actions.empty:
        raise RuntimeError(
            "select_top_acoes() retornou zero ações."
        )

    if "Score" not in top_actions.columns:
        raise RuntimeError(
            "Top ações não possui a coluna 'Score'."
        )

    top_actions["Data Preco"] = data_hoje

    acoes_scores_top = (
        pd.to_numeric(
            top_actions["Score"],
            errors="coerce",
        )
        .reset_index(drop=True)
    )

    if acoes_scores_top.notna().sum() == 0:
        raise RuntimeError(
            "Top ações possui Score, mas todos os Scores são nulos."
        )

    logger.info(
        "Top %d ações selecionadas.",
        len(top_actions),
    )

    # O Investsite entrega a coluna acentuada ("Ação"). Mantemos as grafias
    # compatíveis para que a deduplicação do histórico funcione em ambos os
    # formatos de entrada.
    acao_key = next(
        (
            column
            for column in ("Ação", "Acao", "Ticker")
            if column in top_actions.columns
        ),
        "Ação",
    )

    update_history(
        top_actions,
        os.path.join(
            paths["old_dir"],
            "Top_20_Acoes_BRL.xlsx",
        ),
        key_col=acao_key,
    )

    # Histórico ML — base processada
    try:
        acoes_hist_source = (
            acoes_base
            if acoes_base is not None and not acoes_base.empty
            else df_acoes_raw
        )

        append_historical_data(
            df=acoes_hist_source,
            data_execucao=data_hoje,
            output_file=os.path.join(
                ml_dir,
                "historico_acoes.parquet",
            ),
            subset_cols=["Data_Execucao", "Ação"],
        )

    except Exception as e:
        logger.error(
            f"Falha ao salvar historico ML Acoes: {e}"
        )

    # ── Indicadores de mercado ────────────────────────────────────────────

    try:
        market_data = get_market_indicators()

    except Exception as e:
        logger.error(
            f"Falha ao coletar indicadores de mercado: {e}"
        )
        market_data = {}

    # ── Benchmarks ────────────────────────────────────────────────────────

    try:
        benchmarks = get_benchmarks(meses=13)

    except Exception as e:
        logger.error(
            f"Falha ao coletar benchmarks: {e}"
        )
        benchmarks = {}

    # ── Backtest legado FIIs ──────────────────────────────────────────────

    try:
        backtest = run_backtest(
            os.path.join(
                paths["old_dir"],
                "Top_20_FII_BRL.xlsx",
            ),
            data_fim=data_hoje,
        )

    except Exception as e:
        logger.error(
            f"Falha no backtest Top 20 FIIs: {e}"
        )

        backtest = {
            "disponivel": False,
            "motivo": str(e),
        }

    # ── Carteira histórica ────────────────────────────────────────────────

    carteira_snapshot = pd.DataFrame()

    carteira_path = os.path.join(
        backtest_dir,
        "carteiras_historicas.parquet",
    )
    try:
        save_portfolio_snapshot(
            top_fiis=top_fiis,
            top_acoes=top_actions,
            data_execucao=data_hoje,
            output_file=carteira_path,
        )

        if os.path.exists(carteira_path):
            carteira_all = pd.read_parquet(
                carteira_path
            )

            if "Data_Carteira" in carteira_all.columns:
                carteira_dates = (
                    pd.to_datetime(
                        carteira_all["Data_Carteira"],
                        errors="coerce",
                    )
                    .dt.strftime("%Y-%m-%d")
                )

                carteira_snapshot = carteira_all[
                    carteira_dates.eq(data_hoje)
                ].copy()

    except Exception as e:
        logger.error(
            "Falha ao salvar carteira historica "
            f"de backtest: {e}"
        )

    # ── Data Lake ─────────────────────────────────────────────────────────

    try:
        save_lake_snapshot(
            data_dir=data_dir,
            data_execucao=data_hoje,
            fii_universe=(
                fii_hist_source
                if "fii_hist_source" in locals()
                else df_clean
            ),
            acoes_universe=(
                acoes_hist_source
                if "acoes_hist_source" in locals()
                else df_acoes_raw
            ),
            top_fiis=top_fiis,
            top_acoes=top_actions,
            carteira_snapshot=carteira_snapshot,
        )

    except Exception as e:
        logger.error(
            f"Falha ao salvar snapshot incremental "
            f"do data lake: {e}"
        )

    # ── NOVO: reconstrução dos históricos derivados ──────────────────────
    #
    # O Lake é a fonte oficial dos snapshots.
    # Os arquivos:
    #
    #   data/ml/historico_fiis.parquet
    #   data/ml/historico_acoes.parquet
    #   data/backtest/carteiras_historicas.parquet
    #
    # são derivados.
    #
    # Reconstruí-los aqui garante que o exporter não trabalhe
    # com um histórico antigo/corrompido/acumulado de forma
    # incorreta.

    try:
        rebuild_result = rebuild_legacy_tables_from_lake(
            data_dir=data_dir
        )

        logger.info(
            "Históricos reconstruídos a partir do Data Lake: %s",
            rebuild_result,
        )

    except Exception as e:
        logger.error(
            "Falha ao reconstruir históricos a partir do Data Lake: %s",
            e,
        )

    # ── Datasets e modelos ML ─────────────────────────────────────────────

    try:
        build_all_datasets(
            data_dir=data_dir,
            horizons=(7, 30, 60, 90),
        )

    except Exception as e:
        logger.error(
            f"Falha ao gerar datasets ML: {e}"
        )

    try:
        run_ml_pipeline(
            data_dir=data_dir,
            horizon=30,
        )

    except Exception as e:
        logger.error(
            f"Falha ao executar pipeline ML sombra: {e}"
        )

    # ── Snapshot Excel ───────────────────────────────────────────────────

    snapshot_path = os.path.join(
        paths["output_dir"],
        f"Top20_Ranking_{data_hoje}.xlsx",
    )

    save_snapshot(
        top_actions,
        top_fiis,
        snapshot_path,
    )

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

    # ── Exporta JSON para o dashboard web ─────────────────────────────────

    try:
        export_dashboard_json(
            output_dir=os.path.join(
                "docs",
                "data",
            ),
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
        logger.error(
            f"Falha ao exportar JSON do dashboard: {e}"
        )

    # ── Qualidade ─────────────────────────────────────────────────────────

    try:
        quality_report = run_data_quality_checks(
            data_dir=data_dir,
            dashboard_dir=os.path.join(
                "docs",
                "data",
            ),
        )

        logger.info(
            "Data quality status: "
            f"{quality_report.get('status')}"
        )

    except Exception as e:
        logger.error(
            f"Falha nas checagens de qualidade: {e}"
        )

    # ── Entrega Excel ─────────────────────────────────────────────────────

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
        logger.error(
            f"Falha inesperada na entrega "
            f"do Excel final: {e}"
        )

    logger.info(
        "=== Screener finalizado com sucesso ==="
    )


if __name__ == "__main__":
    main()

"""
dataset_builder.py — Camada 4: Dataset para Machine Learning

Lê os históricos diários em Parquet e gera datasets enriquecidos com retornos
futuros por ativo. Nesta primeira versão, o objetivo é preparar a estrutura
para Random Forest / XGBoost sem depender de serviços pagos.

Entradas esperadas:
- data/ml/historico_fiis.parquet
- data/ml/historico_acoes.parquet

Saídas geradas:
- data/ml/dataset_fiis.parquet
- data/ml/dataset_acoes.parquet

Observação:
Com pouco histórico, as colunas de retorno futuro podem ficar vazias no começo.
Isso é esperado. Conforme novas execuções diárias forem acumuladas, os targets
passam a ser preenchidos automaticamente.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)


FII_ID_COL = "FUNDOS"
FII_DATE_COL = "Data_Execucao"
FII_PRICE_COL = "PREÇO ATUAL (R$)"

ACAO_ID_COL = "Ação"
ACAO_DATE_COL = "Data_Execucao"
ACAO_PRICE_COL = "Preço"

DEFAULT_HORIZONS = (7, 30, 60, 90)


def _safe_read_parquet(path: str) -> pd.DataFrame:
    """Lê um parquet se existir; caso contrário retorna DataFrame vazio."""
    if not os.path.exists(path):
        logger.warning("Arquivo não encontrado: %s", path)
        return pd.DataFrame()

    try:
        return pd.read_parquet(path)
    except Exception as e:
        logger.error("Falha ao ler parquet %s: %s", path, e)
        return pd.DataFrame()


def _validate_required_columns(
    df: pd.DataFrame,
    required_cols: list[str],
    dataset_name: str,
) -> bool:
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        logger.error(
            "%s sem colunas obrigatórias: %s",
            dataset_name,
            missing,
        )
        return False
    return True


def _prepare_base(
    df: pd.DataFrame,
    id_col: str,
    date_col: str,
    price_col: str,
) -> pd.DataFrame:
    """Normaliza ticker, data e preço antes do cálculo de retornos."""
    base = df.copy()

    base[id_col] = base[id_col].astype(str).str.strip().str.upper()
    base[date_col] = pd.to_datetime(base[date_col], errors="coerce")
    base[price_col] = pd.to_numeric(base[price_col], errors="coerce")

    base = base.dropna(subset=[id_col, date_col, price_col])
    base = base[base[id_col] != ""]

    # Se houver mais de uma linha para mesmo ativo/data, mantém a última.
    base = base.sort_values([id_col, date_col])
    base = base.drop_duplicates(subset=[id_col, date_col], keep="last")

    return base


def _add_future_returns(
    df: pd.DataFrame,
    id_col: str,
    date_col: str,
    price_col: str,
    horizons: Iterable[int],
) -> pd.DataFrame:
    """
    Adiciona retorno futuro aproximado por horizonte em dias corridos.

    Para cada ativo e cada data-base, procura a primeira observação disponível
    em data >= Data_Execucao + horizonte. Isso é mais robusto do que exigir
    exatamente D+30, porque o screener não roda em todos os dias corridos.
    """
    result = df.copy()

    for horizon in horizons:
        col_price_future = f"Preco_Futuro_{horizon}d"
        col_date_future = f"Data_Futura_{horizon}d"
        col_return = f"Retorno_Futuro_{horizon}d"

        result[col_price_future] = pd.NA
        result[col_date_future] = pd.NaT
        result[col_return] = pd.NA

    frames = []

    for _, group in result.groupby(id_col, sort=False):
        group = group.sort_values(date_col).copy()
        dates = group[date_col].tolist()
        prices = group[price_col].tolist()

        for idx, row in group.iterrows():
            current_date = row[date_col]
            current_price = row[price_col]

            if pd.isna(current_date) or pd.isna(current_price) or current_price == 0:
                continue

            for horizon in horizons:
                target_date = current_date + pd.Timedelta(days=horizon)

                future_idx = None
                for pos, candidate_date in enumerate(dates):
                    if candidate_date >= target_date:
                        future_idx = pos
                        break

                if future_idx is None:
                    continue

                future_date = dates[future_idx]
                future_price = prices[future_idx]

                if pd.isna(future_price) or future_price == 0:
                    continue

                col_price_future = f"Preco_Futuro_{horizon}d"
                col_date_future = f"Data_Futura_{horizon}d"
                col_return = f"Retorno_Futuro_{horizon}d"

                group.at[idx, col_price_future] = future_price
                group.at[idx, col_date_future] = future_date
                group.at[idx, col_return] = (future_price / current_price) - 1.0

        frames.append(group)

    if not frames:
        return result

    enriched = pd.concat(frames, ignore_index=True)
    enriched = enriched.sort_values([date_col, id_col]).reset_index(drop=True)
    return enriched


def _add_basic_features(
    df: pd.DataFrame,
    id_col: str,
    date_col: str,
    price_col: str,
) -> pd.DataFrame:
    """Cria features simples usando apenas o histórico próprio do projeto."""
    result = df.copy()
    result = result.sort_values([id_col, date_col]).reset_index(drop=True)

    result["Preco_Anterior"] = result.groupby(id_col)[price_col].shift(1)
    result["Retorno_Desde_Snapshot_Anterior"] = (
        result[price_col] / result["Preco_Anterior"] - 1.0
    )

    result["Dias_Desde_Snapshot_Anterior"] = (
        result.groupby(id_col)[date_col].diff().dt.days
    )

    if "Score" in result.columns:
        result["Score_Anterior"] = result.groupby(id_col)["Score"].shift(1)
        result["Delta_Score"] = result["Score"] - result["Score_Anterior"]

    if "Status" in result.columns:
        result["Aprovado_Filtro"] = (
            result["Status"]
            .astype(str)
            .str.upper()
            .str.contains("APROV", na=False)
            .astype(int)
        )

    return result


def build_ml_dataset(
    input_path: str,
    output_path: str,
    id_col: str,
    date_col: str,
    price_col: str,
    dataset_name: str,
    horizons: Iterable[int] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    """Gera um dataset de ML a partir de um histórico de ativos."""
    df = _safe_read_parquet(input_path)
    if df.empty:
        logger.warning("%s vazio — dataset não gerado.", dataset_name)
        return pd.DataFrame()

    required_cols = [id_col, date_col, price_col]
    if not _validate_required_columns(df, required_cols, dataset_name):
        return pd.DataFrame()

    base = _prepare_base(df, id_col=id_col, date_col=date_col, price_col=price_col)
    if base.empty:
        logger.warning("%s sem dados válidos após preparação.", dataset_name)
        return pd.DataFrame()

    enriched = _add_basic_features(
        base,
        id_col=id_col,
        date_col=date_col,
        price_col=price_col,
    )
    enriched = _add_future_returns(
        enriched,
        id_col=id_col,
        date_col=date_col,
        price_col=price_col,
        horizons=horizons,
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    enriched.to_parquet(output_path, index=False)

    logger.info(
        "Dataset ML gerado: %s (%s linhas, %s colunas)",
        output_path,
        len(enriched),
        len(enriched.columns),
    )

    return enriched


def build_all_datasets(
    data_dir: str = "data",
    horizons: Iterable[int] = DEFAULT_HORIZONS,
) -> dict[str, pd.DataFrame]:
    """Gera datasets de FIIs e Ações usando os caminhos padrão do projeto."""
    ml_dir = os.path.join(data_dir, "ml")

    fii_dataset = build_ml_dataset(
        input_path=os.path.join(ml_dir, "historico_fiis.parquet"),
        output_path=os.path.join(ml_dir, "dataset_fiis.parquet"),
        id_col=FII_ID_COL,
        date_col=FII_DATE_COL,
        price_col=FII_PRICE_COL,
        dataset_name="FIIs",
        horizons=horizons,
    )

    acoes_dataset = build_ml_dataset(
        input_path=os.path.join(ml_dir, "historico_acoes.parquet"),
        output_path=os.path.join(ml_dir, "dataset_acoes.parquet"),
        id_col=ACAO_ID_COL,
        date_col=ACAO_DATE_COL,
        price_col=ACAO_PRICE_COL,
        dataset_name="Ações",
        horizons=horizons,
    )

    return {
        "fiis": fii_dataset,
        "acoes": acoes_dataset,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    build_all_datasets()

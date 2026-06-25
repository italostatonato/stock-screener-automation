import logging
import os
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _prepare_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara o DataFrame para salvamento em Parquet.

    Algumas fontes podem trazer colunas object com tipos mistos, por exemplo
    número + texto de rodapé/legenda. O PyArrow não aceita esse tipo misto.
    Para não perder o histórico, convertemos apenas colunas object para string.
    Colunas numéricas já normalizadas permanecem numéricas.
    """
    prepared = df.copy()

    for col in prepared.columns:
        if prepared[col].dtype == "object":
            prepared[col] = prepared[col].astype("string")

    return prepared


def append_historical_data(
    df: pd.DataFrame,
    data_execucao: str,
    output_file: str,
    subset_cols: Optional[list[str]] = None,
) -> None:
    """
    Acrescenta uma base diária ao histórico em Parquet.

    Parâmetros:
        df: DataFrame a ser salvo.
        data_execucao: data da execução no formato YYYY-MM-DD.
        output_file: caminho do arquivo Parquet de saída.
        subset_cols: colunas usadas para remover duplicatas. Se não informado,
            remove duplicatas considerando todas as colunas.
    """
    if df is None or df.empty:
        logger.info("Histórico ML não salvo: DataFrame vazio.")
        return

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    df_hist = df.copy()
    df_hist["Data_Execucao"] = data_execucao
    df_hist = _prepare_for_parquet(df_hist)

    if os.path.exists(output_file):
        historico = pd.read_parquet(output_file)
        historico = _prepare_for_parquet(historico)

        historico = pd.concat(
            [historico, df_hist],
            ignore_index=True,
        )

        if subset_cols:
            existing_subset = [col for col in subset_cols if col in historico.columns]
            if existing_subset:
                historico = historico.drop_duplicates(
                    subset=existing_subset,
                    keep="last",
                )
            else:
                historico = historico.drop_duplicates()
        else:
            historico = historico.drop_duplicates()
    else:
        historico = df_hist

    historico.to_parquet(output_file, index=False)
    logger.info("Histórico ML salvo: %s (%s linhas)", output_file, len(historico))

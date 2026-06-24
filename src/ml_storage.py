import os
import pandas as pd


def append_historical_data(df, data_execucao, output_file):

    if df.empty:
        return

    df_hist = df.copy()
    df_hist["Data_Execucao"] = data_execucao

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    if os.path.exists(output_file):
        historico = pd.read_parquet(output_file)

        historico = pd.concat(
            [historico, df_hist],
            ignore_index=True
        )

        historico = historico.drop_duplicates()

    else:
        historico = df_hist

    historico.to_parquet(
        output_file,
        index=False
    )
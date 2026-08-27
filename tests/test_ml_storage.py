import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ml_storage import _prepare_for_parquet


def test_prepare_for_parquet_recupera_coluna_numerica_gravada_como_texto():
    frame = pd.DataFrame({
        "ROA": ["0.10", "-0.01", None],
        "Ação": ["TEST3", "TEST4", "TEST5"],
    })

    result = _prepare_for_parquet(frame)

    assert pd.api.types.is_numeric_dtype(result["ROA"])
    assert result["ROA"].tolist()[:2] == [0.10, -0.01]
    assert str(result["Ação"].dtype) == "string"

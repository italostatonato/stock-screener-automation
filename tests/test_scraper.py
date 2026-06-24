import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from src.scraper import clean_acoes_raw


def test_clean_acoes_raw_remove_legenda_rodape():
    df = pd.DataFrame({
        "Ação": ["PETR4", "VALE3", "Legenda"],
        "Empresa": ["Petrobras", "Vale", "Texto explicativo das colunas"],
        "Preço": [30.5, 62.1, "Legenda"],
        "Preço/VPA": [1.2, 0.8, None],
    })

    result = clean_acoes_raw(df)

    assert len(result) == 2
    assert list(result["Ação"]) == ["PETR4", "VALE3"]


def test_clean_acoes_raw_remove_preco_nao_numerico():
    df = pd.DataFrame({
        "Ação": ["PETR4", "NOTA"],
        "Empresa": ["Petrobras", "Observação"],
        "Preço": [30.5, "N/D"],
    })

    result = clean_acoes_raw(df)

    assert len(result) == 1
    assert result.iloc[0]["Ação"] == "PETR4"


def test_clean_acoes_raw_vazio():
    assert clean_acoes_raw(pd.DataFrame()).empty

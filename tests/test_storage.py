from pathlib import Path

import pandas as pd

from src.storage import update_history


def test_update_history_deduplicates_accented_action_ticker(tmp_path: Path):
    """O Investsite usa "Ação"; a grafia sem acento não pode duplicar o histórico."""
    history = tmp_path / "Top_20_Acoes_BRL.xlsx"

    first = pd.DataFrame(
        {
            "Ação": ["PETR4"],
            "Preço": [30.0],
            "Data Preco": ["2026-08-26"],
        }
    )
    replacement = pd.DataFrame(
        {
            "Ação": ["PETR4"],
            "Preço": [31.5],
            "Data Preco": ["2026-08-26"],
        }
    )

    update_history(first, str(history), key_col="Ação")
    update_history(replacement, str(history), key_col="Ação")

    saved = pd.read_excel(history)
    assert len(saved) == 1
    assert saved.loc[0, "Ação"] == "PETR4"
    assert saved.loc[0, "Preço"] == 31.5

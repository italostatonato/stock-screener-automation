import pandas as pd
import pytest

from src.scorer import (
    ACOES_DIRECTION,
    ACOES_WEIGHTS,
    FII_DIRECTION,
    FII_WEIGHTS,
    _percentil_score,
    score_fiis,
)


def test_fiis_usam_a_selecao_com_pesos_iguais():
    assert list(FII_WEIGHTS) == [
        "DY (12M) MÉDIA",
        "P/VP",
        "LIQUIDEZ DIÁRIA (R$)",
        "PATRIMÔNIO LÍQUIDO",
        "RENTAB. PERÍODO",
        "TAX. ADMINISTRAÇÃO",
        "TAX. PERFORMANCE",
    ]
    assert FII_DIRECTION == {
        "DY (12M) MÉDIA": "max",
        "P/VP": "min",
        "LIQUIDEZ DIÁRIA (R$)": "max",
        "PATRIMÔNIO LÍQUIDO": "max",
        "RENTAB. PERÍODO": "max",
        "TAX. ADMINISTRAÇÃO": "min",
        "TAX. PERFORMANCE": "min",
    }
    assert sum(FII_WEIGHTS.values()) == pytest.approx(1.0)
    assert all(weight == pytest.approx(1 / 7) for weight in FII_WEIGHTS.values())


def test_acoes_usam_a_selecao_com_pesos_iguais():
    assert list(ACOES_WEIGHTS) == [
        "Dividend Yield",
        "Preço/VPA",
        "EV/EBITDA",
        "Margem Líquida",
        "ROInvC",
        "RPL",
        "Volume Diário Médio (3 meses)",
    ]
    assert ACOES_DIRECTION == {
        "Dividend Yield": "max",
        "Preço/VPA": "min",
        "EV/EBITDA": "min",
        "Margem Líquida": "max",
        "ROInvC": "max",
        "RPL": "max",
        "Volume Diário Médio (3 meses)": "max",
    }
    assert sum(ACOES_WEIGHTS.values()) == pytest.approx(1.0)
    assert all(weight == pytest.approx(1 / 7) for weight in ACOES_WEIGHTS.values())


@pytest.mark.parametrize("direction", ["max", "min"])
def test_dado_ausente_recebe_percentil_neutro(direction):
    scores = _percentil_score(pd.Series([1.0, 3.0, None]), direction)
    assert scores.iloc[2] == pytest.approx(50.0)
    assert scores.iloc[2] <= scores.max()


def test_coluna_inteira_ausente_mantem_seu_setimo_como_neutro():
    df = pd.DataFrame({"P/VP": [1.0, 2.0]})
    scores = score_fiis(df)
    assert scores.iloc[0] == pytest.approx(50.0)
    assert scores.iloc[1] == pytest.approx(42.9)

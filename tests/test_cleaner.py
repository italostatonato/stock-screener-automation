import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from src.cleaner import (
    _parse_percent,
    _parse_money,
    _parse_float,
    _parse_integer,
    clean_and_normalize,
)


# ── _parse_percent ──────────────────────────────────────────────────────────

def test_parse_percent_basico():
    s = pd.Series(["4,5%", "10,00%", "0,89%"])
    result = _parse_percent(s)
    assert result.iloc[0] == pytest.approx(0.045)
    assert result.iloc[1] == pytest.approx(0.10)
    assert result.iloc[2] == pytest.approx(0.0089)


def test_parse_percent_com_milhar():
    s = pd.Series(["1.234,56%"])
    result = _parse_percent(s)
    assert result.iloc[0] == pytest.approx(12.3456)


def test_parse_percent_invalidos():
    s = pd.Series(["N/A", "nan", "None", ""])
    result = _parse_percent(s)
    assert result.isna().all()


def test_parse_percent_zero():
    s = pd.Series(["0,00%"])
    result = _parse_percent(s)
    assert result.iloc[0] == 0.0


# ── _parse_money ─────────────────────────────────────────────────────────────

def test_parse_money_basico():
    s = pd.Series(["R$ 1.234,56", "R$ 100,00"])
    result = _parse_money(s)
    assert result.iloc[0] == pytest.approx(1234.56)
    assert result.iloc[1] == pytest.approx(100.00)


def test_parse_money_sem_simbolo():
    s = pd.Series(["1.548,74"])
    result = _parse_money(s)
    assert result.iloc[0] == pytest.approx(1548.74)


def test_parse_money_negativo():
    s = pd.Series(["-2.623.807,00"])
    result = _parse_money(s)
    assert result.iloc[0] == pytest.approx(-2623807.00)


def test_parse_money_invalidos():
    s = pd.Series(["N/A", "", "None"])
    result = _parse_money(s)
    assert result.isna().all()


# ── _parse_float ─────────────────────────────────────────────────────────────

def test_parse_float_basico():
    s = pd.Series(["1,05", "0,88", "285,33"])
    result = _parse_float(s)
    assert result.iloc[0] == pytest.approx(1.05)
    assert result.iloc[1] == pytest.approx(0.88)
    assert result.iloc[2] == pytest.approx(285.33)


def test_parse_float_invalido():
    s = pd.Series(["N/A"])
    result = _parse_float(s)
    assert result.isna().all()


# ── _parse_integer ───────────────────────────────────────────────────────────

def test_parse_integer_com_milhar():
    s = pd.Series(["30.949", "1.000.000"])
    result = _parse_integer(s)
    assert result.iloc[0] == 30949
    assert result.iloc[1] == 1000000


def test_parse_integer_invalido():
    s = pd.Series(["N/A", ""])
    result = _parse_integer(s)
    assert result.isna().all()


# ── clean_and_normalize (integração) ─────────────────────────────────────────

def test_clean_and_normalize_completo():
    df_raw = pd.DataFrame({
        "FUNDOS": ["AAGR11", "AAZQ11"],
        "DIVIDEND YIELD": ["1,55 %", "1,15 %"],
        "PREÇO ATUAL (R$)": ["125,99", "7,53"],
        "P/VP": ["N/A", "0,88"],
        "QUANT. ATIVOS": ["0", "30.949"],
        "VOLATILIDADE": ["5.447,16", "1.548,74"],
    })

    col_cfg = {
        "percent": ["DIVIDEND YIELD"],
        "money": ["PREÇO ATUAL (R$)"],
        "integer": ["QUANT. ATIVOS"],
        "float_simple": ["VOLATILIDADE"],
    }

    result = clean_and_normalize(df_raw, col_cfg)

    assert result["DIVIDEND YIELD"].iloc[0] == pytest.approx(0.0155)
    assert result["PREÇO ATUAL (R$)"].iloc[0] == pytest.approx(125.99)
    assert pd.isna(result["P/VP"].iloc[0])
    assert result["P/VP"].iloc[1] == pytest.approx(0.88)
    assert result["VOLATILIDADE"].iloc[1] == pytest.approx(1548.74)
    # coluna não mapeada (FUNDOS) deve permanecer intacta
    assert result["FUNDOS"].iloc[0] == "AAGR11"


def test_clean_and_normalize_strip_espacos():
    df_raw = pd.DataFrame({
        "FUNDOS": ["  AAGR11  ", "AAZQ11"],
    })
    result = clean_and_normalize(df_raw, {})
    assert result["FUNDOS"].iloc[0] == "AAGR11"

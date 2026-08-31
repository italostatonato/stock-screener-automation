import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from src.filters import select_top_fiis, select_top_acoes


def _make_fii_df(n=20):
    """Gera um DataFrame sintético de FIIs com variação suficiente para quartis."""
    import numpy as np
    np.random.seed(42)
    return pd.DataFrame({
        "FUNDOS": [f"FII{i:02d}11" for i in range(n)],
        "P/VP": np.round(np.random.uniform(0.5, 1.5, n), 2),
        "DIVIDEND YIELD": np.round(np.random.uniform(0.01, 0.15, n), 4),
        "DY (12M) MÉDIA": np.round(np.random.uniform(0.01, 0.15, n), 4),
        "LIQUIDEZ DIÁRIA (R$)": np.round(np.random.uniform(50_000, 2_000_000, n), 2),
        "PATRIMÔNIO LÍQUIDO": np.round(np.random.uniform(50_000_000, 1_000_000_000, n), 2),
        "VOLATILIDADE": np.round(np.random.uniform(5, 100, n), 2),
        "Score": np.round(np.random.uniform(0, 100, n), 1),
    })


def _base_cfg():
    return {
        "filters": {
            "dy_min": 0.003,
            "liquidez_min": 10_000,
            "patrimonio_min": 10_000_000,
            "top_n": 5,
            "acoes": {
                "dy_min": 0.01,
                "volume_min": 10_000,
                "market_cap_min": 10_000_000,
                "top_n": 5,
            },
        }
    }


# ── select_top_fiis ───────────────────────────────────────────────────────────

def test_select_top_fiis_retorna_dois_dataframes():
    df = _make_fii_df()
    cfg = _base_cfg()
    top, base = select_top_fiis(df, cfg)
    assert isinstance(top, pd.DataFrame)
    assert isinstance(base, pd.DataFrame)


def test_select_top_fiis_respeita_top_n():
    df = _make_fii_df(n=30)
    cfg = _base_cfg()
    top, base = select_top_fiis(df, cfg)
    assert len(top) <= cfg["filters"]["top_n"]


def test_select_top_fiis_base_tem_status():
    df = _make_fii_df()
    cfg = _base_cfg()
    top, base = select_top_fiis(df, cfg)
    assert "Status" in base.columns
    assert base["Status"].notna().all()


def test_select_top_fiis_base_preserva_todas_linhas():
    df = _make_fii_df(n=15)
    cfg = _base_cfg()
    top, base = select_top_fiis(df, cfg)
    assert len(base) == 15


def test_select_top_fiis_coluna_ausente_lanca_erro():
    df = pd.DataFrame({"FUNDOS": ["AAGR11"]})  # faltam colunas obrigatórias
    cfg = _base_cfg()
    with pytest.raises(ValueError):
        select_top_fiis(df, cfg)


def test_select_top_fiis_filtro_fixo_elimina_dy_baixo():
    df = _make_fii_df()
    df.loc[0, "DY (12M) MÉDIA"] = 0.001  # abaixo do mínimo fixo
    cfg = _base_cfg()
    top, base = select_top_fiis(df, cfg)
    status_linha_0 = base.loc[base["FUNDOS"] == "FII0011", "Status"].iloc[0]
    assert "Eliminado no filtro fixo" in status_linha_0


def test_select_top_fiis_ordenacao_por_score_desc():
    df = _make_fii_df(n=30)
    cfg = _base_cfg()
    top, base = select_top_fiis(df, cfg)
    if len(top) > 1:
        scores = top["Score"].tolist()
        assert scores == sorted(scores, reverse=True)


def test_select_top_fiis_nao_usa_volatilidade_ou_dy_mensal_como_filtro():
    df = _make_fii_df()
    df.loc[0, "DIVIDEND YIELD"] = None
    df.loc[0, "VOLATILIDADE"] = None
    _, base = select_top_fiis(df, _base_cfg())
    status = base.loc[base["FUNDOS"] == "FII0011", "Status"].iloc[0]
    assert not status.startswith("Eliminado")


# ── select_top_acoes ──────────────────────────────────────────────────────────

def _make_acoes_df(n=20):
    import numpy as np
    np.random.seed(42)
    return pd.DataFrame({
        "Ação": [f"ACAO{i}3" for i in range(n)],
        "Empresa": [f"Empresa {i}" for i in range(n)],
        "Preço": np.round(np.random.uniform(5, 100, n), 2),
        "Preço/VPA": np.round(np.random.uniform(0.3, 3.0, n), 2),
        "Preço/Lucro": np.round(np.random.uniform(3, 20, n), 2),
        "EV/EBIT": np.round(np.random.uniform(2, 15, n), 2),
        "EV/EBITDA": np.round(np.random.uniform(2, 12, n), 2),
        "Margem Líquida": np.round(np.random.uniform(0.01, 0.30, n), 4),
        "ROA": np.round(np.random.uniform(0.01, 0.15, n), 4),
        "RPL": np.round(np.random.uniform(0.05, 0.30, n), 4),
        "ROInvC": np.round(np.random.uniform(0.02, 0.20, n), 4),
        "Passivo/Patrimônio Líquido": np.round(np.random.uniform(0.2, 2.0, n), 2),
        "Alavancagem Financeira": np.round(np.random.uniform(0.5, 4.0, n), 2),
        "Dividend Yield": np.round(np.random.uniform(0.01, 0.10, n), 4),
        "Volume Diário Médio (3 meses)": np.round(np.random.uniform(100_000, 5_000_000, n), 2),
        "Market Cap Empresa": np.round(np.random.uniform(50_000_000, 5_000_000_000, n), 2),
    })


def test_select_top_acoes_retorna_dois_dataframes():
    df = _make_acoes_df()
    cfg = _base_cfg()
    top, base = select_top_acoes(df, cfg)
    assert isinstance(top, pd.DataFrame)
    assert isinstance(base, pd.DataFrame)


def test_select_top_acoes_respeita_top_n():
    df = _make_acoes_df(n=30)
    cfg = _base_cfg()
    top, base = select_top_acoes(df, cfg)
    assert len(top) <= cfg["filters"]["acoes"]["top_n"]


def test_select_top_acoes_base_tem_status():
    df = _make_acoes_df()
    cfg = _base_cfg()
    top, base = select_top_acoes(df, cfg)
    assert "Status" in base.columns
    assert base["Status"].notna().all()


def test_select_top_acoes_remove_duplicatas_empresa():
    df = _make_acoes_df(n=5)
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # duplica a primeira empresa
    cfg = _base_cfg()
    top, base = select_top_acoes(df, cfg)
    assert base["Empresa"].duplicated().sum() == 0


def test_select_top_acoes_remove_classes_da_mesma_companhia_e_mantem_maior_score():
    df = _make_acoes_df(n=8)
    df.loc[0, ["Ação", "Empresa"]] = ["PETR3", "PETR3"]
    df.loc[1, ["Ação", "Empresa"]] = ["PETR4", "PETR4"]
    df["Score"] = [80.0, 90.0, 70.0, 60.0, 50.0, 40.0, 30.0, 20.0]

    top, base = select_top_acoes(df, _base_cfg())

    assert "PETR4" in set(top["Ação"])
    assert "PETR3" not in set(top["Ação"])
    status_petr3 = base.loc[base["Ação"] == "PETR3", "Status"].iloc[0]
    assert status_petr3 == "Eliminado por duplicidade da empresa"


def test_select_top_acoes_tambem_deduplica_nome_real_normalizado():
    df = _make_acoes_df(n=8)
    df.loc[0, ["Ação", "Empresa"]] = ["ABCD3", "Companhia Exemplo ON"]
    df.loc[1, ["Ação", "Empresa"]] = ["WXYZ4", "Companhia Exemplo PN"]
    df["Score"] = [80.0, 90.0, 70.0, 60.0, 50.0, 40.0, 30.0, 20.0]

    top, _ = select_top_acoes(df, _base_cfg())

    selected = set(top["Ação"])
    assert "WXYZ4" in selected
    assert "ABCD3" not in selected


def test_select_top_acoes_dropna_preco():
    df = _make_acoes_df(n=5)
    df.loc[0, "Preço"] = None
    cfg = _base_cfg()
    top, base = select_top_acoes(df, cfg)
    assert len(base) == 4  # a linha com Preço nulo é descartada antes do status


def test_select_top_acoes_nao_exige_indicadores_fora_do_score():
    df = _make_acoes_df().drop(columns=[
        "Preço/Lucro",
        "EV/EBIT",
        "ROA",
        "Passivo/Patrimônio Líquido",
        "Alavancagem Financeira",
    ])
    top, base = select_top_acoes(df, _base_cfg())
    assert not top.empty
    assert base["Status"].notna().all()


def test_select_top_acoes_ordenacao_por_score_desc():
    df = _make_acoes_df(n=30)
    df["Score"] = list(range(30))
    top, _ = select_top_acoes(df, _base_cfg())
    assert top["Score"].tolist() == sorted(top["Score"], reverse=True)

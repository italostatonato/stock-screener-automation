from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from src.point_in_time import (
    build_fii_universe_as_of,
    load_fii_backfill_portfolios,
    load_cvm_fii_archive,
    monthly_signal_dates,
    select_available_as_of,
    source_manifest,
)


def test_select_available_as_of_impede_lookahead():
    frame = pd.DataFrame(
        {
            "CNPJ": ["1", "1", "1", "2"],
            "Data_Referencia": ["2025-12-31", "2025-12-31", "2026-03-31", "2025-12-31"],
            "Data_Disponibilidade": ["2026-02-01", "2026-02-10", "2026-05-15", "2026-04-01"],
            "Versao": [1, 2, 1, 1],
            "Valor": [10, 11, 99, 20],
        }
    )
    selected = select_available_as_of(frame, "2026-03-31", entity_col="CNPJ")
    assert selected[["CNPJ", "Valor"]].to_dict("records") == [{"CNPJ": "1", "Valor": 11}]


def test_monthly_signal_dates_usa_ultimo_pregao():
    prices = pd.DataFrame(
        {"Data": pd.to_datetime(["2026-01-29", "2026-01-30", "2026-02-27"]), "Ticker": ["A", "A", "A"]}
    )
    assert monthly_signal_dates(prices, "2026-01-01", "2026-02-28") == [
        pd.Timestamp("2026-01-30"),
        pd.Timestamp("2026-02-27"),
    ]


def test_load_cvm_fii_archive_preserva_data_entrega(tmp_path: Path):
    archive = tmp_path / "fii.zip"
    geral = pd.DataFrame(
        {
            "CNPJ_Fundo_Classe": ["1"], "Data_Referencia": ["2026-01-01"], "Versao": [1],
            "Data_Entrega": ["2026-03-15"], "Nome_Fundo_Classe": ["Fundo"], "Codigo_ISIN": ["BRTESTCTF001"],
        }
    )
    complemento = pd.DataFrame(
        {
            "CNPJ_Fundo_Classe": ["1"], "Data_Referencia": ["2026-01-01"], "Versao": [1],
            "Patrimonio_Liquido": [1000], "Cotas_Emitidas": [100], "Valor_Patrimonial_Cotas": [10],
            "Percentual_Dividend_Yield_Mes": [0.01], "Total_Numero_Cotistas": [50],
        }
    )
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipped:
        zipped.writestr("inf_mensal_fii_geral_2026.csv", geral.to_csv(sep=";", index=False))
        zipped.writestr("inf_mensal_fii_complemento_2026.csv", complemento.to_csv(sep=";", index=False))
    out = load_cvm_fii_archive(archive)
    assert out.iloc[0]["Data_Disponibilidade"] == pd.Timestamp("2026-03-15")


def test_build_universe_usa_fundamento_ja_publicado():
    fundamentals = pd.DataFrame(
        {
            "CNPJ": ["1", "1"], "ISIN": ["BRTESTCTF001"] * 2, "Nome": ["Fundo"] * 2,
            "Data_Referencia": pd.to_datetime(["2025-12-01", "2026-01-01"]),
            "Data_Disponibilidade": pd.to_datetime(["2026-02-01", "2026-04-01"]),
            "Versao": [1, 1], "PATRIMÔNIO LÍQUIDO": [1000, 2000], "Cotas_Emitidas": [100, 100],
            "VPA": [10, 20], "DIVIDEND YIELD": [0.01, 0.02], "NUM. COTISTAS": [50, 60],
            "Fonte_Fundamento": ["CVM"] * 2,
        }
    )
    dates = pd.date_range("2026-01-02", periods=40, freq="B")
    prices = pd.DataFrame(
        {
            "Data": dates, "Ticker": ["TEST11"] * len(dates), "ISIN": ["BRTESTCTF001"] * len(dates),
            "PREÇO ATUAL (R$)": range(10, 10 + len(dates)), "Volume_Financeiro": [200000] * len(dates),
            "Fonte_Preco": ["B3"] * len(dates),
        }
    )
    out = build_fii_universe_as_of("2026-03-01", fundamentals, prices)
    assert out.iloc[0]["VPA"] == 10
    assert out.iloc[0]["Data_Disponibilidade"] == pd.Timestamp("2026-02-01")


def test_load_backfill_portfolios_preserva_natureza_e_completude(tmp_path: Path):
    snapshot = tmp_path / "snapshots" / "2026-01-30"
    snapshot.mkdir(parents=True)
    pd.DataFrame({"FUNDOS": ["TEST11"], "Score": [88.0]}).to_parquet(
        snapshot / "top_fiis.parquet", index=False
    )
    (snapshot / "manifest.json").write_text(
        '{"carteira_completa": false, "strategy_version": "fii_test"}',
        encoding="utf-8",
    )

    out = load_fii_backfill_portfolios(tmp_path)

    assert out.iloc[0]["Ticker"] == "TEST11"
    assert not bool(out.iloc[0]["Tipo_Completo"])
    assert out.iloc[0]["Natureza"] == "SIMULADO_POINT_IN_TIME"
    assert out.iloc[0]["Strategy_Version"] == "fii_test"


def test_source_manifest_usa_caminho_relativo_e_hash(tmp_path: Path):
    raw = tmp_path / "data" / "raw" / "source.zip"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"conteudo")

    item = source_manifest([raw], relative_to=tmp_path)[0]

    assert item["path"] == "data/raw/source.zip"
    assert item["bytes"] == 8
    assert len(item["sha256"]) == 64

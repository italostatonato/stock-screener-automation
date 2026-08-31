import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest
import requests
from selenium.common.exceptions import TimeoutException

from src.scraper import (
    _build_brapi_acoes_frame,
    _load_page,
    _raise_if_investsite_login_required,
    _wait_for_excel_download,
    build_fundamentus_acoes_frame,
    clean_acoes_raw,
    scrape_acoes,
    scrape_acoes_fundamentus,
    validate_brapi_access,
)


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


def test_wait_for_excel_download_aceita_arquivo_da_execucao(tmp_path):
    started_at = time.time()
    downloaded = tmp_path / "acoes.xlsx"
    downloaded.write_bytes(b"conteudo de teste")

    result = _wait_for_excel_download(
        download_dir=str(tmp_path),
        started_at=started_at,
        timeout=0.1,
    )

    assert result == str(downloaded)


def test_load_page_interrompe_recursos_apos_timeout():
    class Driver:
        def __init__(self):
            self.timeout = None
            self.stopped = False

        def set_page_load_timeout(self, timeout):
            self.timeout = timeout

        def get(self, url):
            raise TimeoutException("página ainda carregando")

        def execute_script(self, script):
            self.stopped = script == "window.stop();"

    driver = Driver()

    _load_page(driver, "https://example.test", timeout=12)

    assert driver.timeout == 12
    assert driver.stopped


def test_investsite_login_gera_erro_explicito():
    class Driver:
        current_url = "https://www.investsite.com.br/login.php"

    with pytest.raises(PermissionError, match="página de login"):
        _raise_if_investsite_login_required(Driver())


def test_investsite_pagina_de_dados_nao_gera_erro():
    class Driver:
        current_url = "https://www.investsite.com.br/seleciona_acoes.php"

    _raise_if_investsite_login_required(Driver())


def test_brapi_mapeia_campos_exigidos_pelo_ranking_de_acoes():
    listings = [{
        "stock": "TEST3",
        "name": "Empresa Teste",
        "close": 20.0,
        "market_cap": 1_000.0,
    }]
    statistics = {"TEST3": {
        "priceToBook": 1.25,
        "trailingPE": 8.0,
        "enterpriseValue": 1_200.0,
        "enterpriseToEbitda": 6.0,
        "enterpriseToRevenue": 1.5,
        "dividendYield": 0.08,
        "sharesOutstanding": 50.0,
    }}
    financial = {"TEST3": {
        "returnOnEquity": 0.20,
        "returnOnAssets": 0.10,
        "profitMargins": 0.15,
        "grossMargins": 0.40,
        "operatingMargins": 0.22,
        "totalRevenue": 800.0,
        "totalDebt": 300.0,
        "totalCash": 50.0,
        "freeCashflow": 100.0,
        "operatingCashflow": 150.0,
    }}
    income = {"TEST3": [
        {"endDate": f"202{year}-12-31", "ebit": 50.0, "cleanNopat": 33.0}
        for year in range(6, 2, -1)
    ]}
    balance = {"TEST3": [{
        "endDate": "2026-06-30",
        "totalAssets": 1_000.0,
        "totalLiab": 600.0,
        "shareholdersEquity": 400.0,
    }]}
    history = {"TEST3": {
        "historicalDataPrice": [{"volume": 100.0}, {"volume": 300.0}],
    }}

    result = _build_brapi_acoes_frame(
        listings, statistics, financial, income, balance, history,
    )

    assert {
        "Ação", "Empresa", "Preço", "Preço/VPA", "Preço/Lucro",
        "EV/EBIT", "EV/EBITDA", "Margem Líquida", "ROA", "RPL",
        "ROInvC", "Passivo/Patrimônio Líquido",
        "Alavancagem Financeira", "Dividend Yield",
        "Volume Diário Médio (3 meses)", "Market Cap Empresa",
    }.issubset(result.columns)

    row = result.iloc[0]
    assert row["Ação"] == "TEST3"
    assert row["Preço"] == 20.0
    assert row["Preço/VPA"] == 1.25
    assert row["Preço/Lucro"] == 8.0
    assert row["EV/EBIT"] == 6.0
    assert row["EV/EBITDA"] == 6.0
    assert row["ROA"] == 0.10
    assert row["RPL"] == 0.20
    assert row["Alavancagem Financeira"] == 2.5
    assert row["Passivo/Patrimônio Líquido"] == 1.5
    assert row["Volume Diário Médio (3 meses)"] == 200.0


def test_brapi_plano_nao_pro_falha_antes_da_coleta(monkeypatch):
    monkeypatch.setattr(
        "src.scraper._brapi_get",
        lambda *args, **kwargs: {"usage": {"planName": "free"}},
    )

    with pytest.raises(PermissionError, match="plano free"):
        validate_brapi_access({"brapi_token": "token-de-teste"})


def test_brapi_plano_pro_passa_na_validacao(monkeypatch):
    monkeypatch.setattr(
        "src.scraper._brapi_get",
        lambda *args, **kwargs: {"usage": {"planName": "pro"}},
    )

    assert validate_brapi_access({"brapi_token": "token-de-teste"}) == "pro"


def test_fundamentus_mapeia_campos_exigidos_pelo_ranking_de_acoes():
    raw = pd.DataFrame({
        "Papel": ["TEST3"],
        "Cotação": ["20,00"],
        "P/L": ["8,00"],
        "P/VP": ["1,25"],
        "Div.Yield": ["8,00%"],
        "P/Ativo": ["0,80"],
        "EV/EBIT": ["6,00"],
        "EV/EBITDA": ["6,00"],
        "Mrg. Líq.": ["15,00%"],
        "ROIC": ["12,00%"],
        "ROE": ["20,00%"],
        "Liq.2meses": ["1.200.000,00"],
        "Patrim. Líq": ["800.000.000,00"],
        "Dív.Líq/ Patrim.": ["0,50"],
    })

    result = build_fundamentus_acoes_frame(raw)

    assert {
        "Ação", "Empresa", "Preço", "Preço/VPA", "Preço/Lucro",
        "EV/EBIT", "EV/EBITDA", "Margem Líquida", "ROA", "RPL",
        "ROInvC", "Passivo/Patrimônio Líquido",
        "Alavancagem Financeira", "Dividend Yield",
        "Volume Diário Médio (3 meses)", "Market Cap Empresa",
    }.issubset(result.columns)

    row = result.iloc[0]
    assert row["Ação"] == "TEST3"
    assert row["Preço"] == 20.0
    assert row["Margem Líquida"] == 0.15
    assert row["ROA"] == 0.10
    assert row["RPL"] == 0.20
    assert row["Alavancagem Financeira"] == 1.5
    assert row["Volume Diário Médio (3 meses)"] == 1_200_000.0
    assert row["Market Cap Empresa"] == 1_000_000_000.0


def test_fonte_padrao_de_acoes_e_fundamentus_sem_token(monkeypatch):
    expected = pd.DataFrame({"Ação": ["TEST3"]})
    monkeypatch.setattr(
        "src.scraper.scrape_acoes_fundamentus",
        lambda cfg: expected,
    )

    result = scrape_acoes({})

    assert result is expected


def test_fundamentus_html_preserva_virgula_decimal(monkeypatch):
    headers = [
        "Papel", "Cotação", "P/L", "P/VP", "Div.Yield", "P/Ativo",
        "EV/EBIT", "EV/EBITDA", "Mrg. Líq.", "ROIC", "ROE",
        "Liq.2meses", "Patrim. Líq", "Dív.Líq/ Patrim.",
    ]
    values = [
        "TEST3", "20,00", "8,00", "0,75", "8,00%", "0,80",
        "6,00", "6,00", "15,00%", "12,00%", "20,00%",
        "1.200.000,00", "800.000.000,00", "0,50",
    ]
    html = (
        "<table><thead><tr>"
        + "".join(f"<th>{header}</th>" for header in headers)
        + "</tr></thead><tbody><tr>"
        + "".join(f"<td>{value}</td>" for value in values)
        + "</tr></tbody></table>"
    )

    class Response:
        text = html

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr("src.scraper.requests.get", lambda *args, **kwargs: Response())

    result = scrape_acoes_fundamentus({})

    row = result.iloc[0]
    assert row["Preço/VPA"] == 0.75
    assert row["Preço/Lucro"] == 8.0
    assert row["ROA"] == 0.10
    assert row["Volume Diário Médio (3 meses)"] == 1_200_000.0


def test_fundamentus_repete_requisicao_apos_timeout(monkeypatch):
    raw = pd.DataFrame({
        "Papel": ["TEST3"],
        "Cotação": ["20,00"],
        "P/L": ["8,00"],
        "P/VP": ["0,75"],
        "Div.Yield": ["8,00%"],
        "P/Ativo": ["0,80"],
        "EV/EBIT": ["6,00"],
        "EV/EBITDA": ["6,00"],
        "Mrg. Líq.": ["15,00%"],
        "ROIC": ["12,00%"],
        "ROE": ["20,00%"],
        "Liq.2meses": ["1.200.000,00"],
        "Patrim. Líq": ["800.000.000,00"],
        "Dív.Líq/ Patrim.": ["0,50"],
    })
    attempts = []

    class Response:
        text = "<table></table>"

        @staticmethod
        def raise_for_status():
            return None

    def fake_get(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise requests.Timeout("fonte lenta")
        return Response()

    monkeypatch.setattr("src.scraper.requests.get", fake_get)
    monkeypatch.setattr("src.scraper.pd.read_html", lambda *args, **kwargs: [raw])
    monkeypatch.setattr("src.scraper.time.sleep", lambda *_: None)

    result = scrape_acoes_fundamentus({"fundamentus_retries": 1})

    assert len(attempts) == 2
    assert result.iloc[0]["Ação"] == "TEST3"

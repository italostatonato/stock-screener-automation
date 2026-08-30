from src.exporter import _enrich_asset_names


def test_enrich_asset_names_substitui_ticker_e_preserva_nome_anterior():
    fiis, acoes = _enrich_asset_names(
        fiis_records=[{"FUNDOS": "KOPA11", "SETOR": "PAPÉIS"}],
        acoes_records=[{"Ação": "PETR4", "Empresa": "PETR4"}],
        market_data={
            "asset_names": {
                "KOPA11": "Kinea Oportunidades Agro I Fiagro",
                "PETR4": "Petróleo Brasileiro S.A. Petrobras",
            }
        },
        prev_data={},
    )

    assert fiis[0]["NOME"] == "Kinea Oportunidades Agro I Fiagro"
    assert acoes[0]["Empresa"] == "Petróleo Brasileiro S.A. Petrobras"

    fiis, acoes = _enrich_asset_names(
        fiis_records=[{"FUNDOS": "KOPA11"}],
        acoes_records=[{"Ação": "PETR4", "Empresa": "PETR4"}],
        market_data={},
        prev_data={"fiis": fiis, "acoes": acoes},
    )

    assert fiis[0]["NOME"] == "Kinea Oportunidades Agro I Fiagro"
    assert acoes[0]["Empresa"] == "Petróleo Brasileiro S.A. Petrobras"

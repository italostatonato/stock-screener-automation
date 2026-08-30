from datetime import datetime, timedelta

from src.market_data import (
    _fetch_asset_names,
    _fetch_bcb_series,
    _fetch_coingecko_top_cryptos,
    _fetch_frankfurter_cambio,
)


def test_fetch_bcb_series_descarta_observacoes_futuras(monkeypatch):
    today = datetime.today().date()
    payload = [
        {"data": today.strftime("%d/%m/%Y"), "valor": "10,50"},
        {
            "data": (today + timedelta(days=7)).strftime("%d/%m/%Y"),
            "valor": "11,00",
        },
    ]

    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return payload

    monkeypatch.setattr("src.market_data.requests.get", lambda *args, **kwargs: Response())

    result = _fetch_bcb_series(13522, meses=1)

    assert len(result) == 1
    assert result.iloc[0]["valor"] == 10.50
    assert result.iloc[0]["data"].date() == today


def test_fetch_coingecko_top_cryptos_normaliza_e_limita(monkeypatch):
    payload = [
        {
            "id": f"coin-{rank}",
            "symbol": f"c{rank}",
            "name": f"Coin {rank}",
            "market_cap_rank": rank,
            "current_price": 1000 * rank,
            "price_change_percentage_24h": rank / 10,
            "market_cap": 1_000_000 / rank,
            "image": f"https://example.com/{rank}.png",
            "last_updated": "2026-08-29T12:00:00Z",
        }
        for rank in range(1, 8)
    ]

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return payload

    monkeypatch.setattr("src.market_data.requests.get", lambda *args, **kwargs: Response())

    result = _fetch_coingecko_top_cryptos(limit=5)

    assert len(result) == 5
    assert result[0]["simbolo"] == "C1"
    assert result[0]["ranking_market_cap"] == 1
    assert result[0]["preco_brl"] == 1000.0
    assert result[-1]["nome"] == "Coin 5"


def test_fetch_frankfurter_cambio_inverte_taxa_brl(monkeypatch):
    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "date": "2026-08-28",
                "rates": {"USD": 0.2, "EUR": 0.16, "GBP": 0.14},
            }

    monkeypatch.setattr("src.market_data.requests.get", lambda *args, **kwargs: Response())

    result = _fetch_frankfurter_cambio()

    assert result["USD/BRL"]["valor"] == 5.0
    assert result["EUR/BRL"]["valor"] == 6.25
    assert result["GBP/BRL"]["atualizado_em"] == "2026-08-28"
    assert result["USD/BRL"]["fonte"] == "Frankfurter"


def test_fetch_asset_names_combina_brapi_e_yahoo(monkeypatch):
    monkeypatch.setattr(
        "src.market_data._asset_name_from_brapi",
        lambda ticker: "Petróleo Brasileiro S.A. Petrobras" if ticker == "PETR4" else None,
    )
    monkeypatch.setattr(
        "src.market_data._asset_name_from_yahoo",
        lambda ticker: "Kinea Oportunidades Agro I Fiagro" if ticker == "KOPA11" else None,
    )

    result = _fetch_asset_names(["petr4", "KOPA11", "PETR4"], workers=2)

    assert result == {
        "KOPA11": "Kinea Oportunidades Agro I Fiagro",
        "PETR4": "Petróleo Brasileiro S.A. Petrobras",
    }

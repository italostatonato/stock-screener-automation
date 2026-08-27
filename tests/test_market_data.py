from datetime import datetime, timedelta

from src.market_data import _fetch_bcb_series


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

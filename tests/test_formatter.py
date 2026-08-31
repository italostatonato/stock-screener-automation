from openpyxl import Workbook

from src.formatter import _add_indicadores


def test_add_indicadores_aceita_cambio_sem_variacao_diaria():
    wb = Workbook()

    _add_indicadores(
        wb,
        {
            "cambio": {
                "USD/BRL": {
                    "valor": 5.19,
                    "variacao_pct": None,
                }
            }
        },
    )

    ws = wb["Indicadores"]
    assert ws["B5"].value == 5.19
    assert ws["C5"].value is None

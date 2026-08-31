import json

from src.exporter import rebuild_dashboard_kpi_history


def test_rebuild_dashboard_kpi_history_gera_payload_compacto(tmp_path):
    (tmp_path / "2026-08-30.json").write_text(
        json.dumps(
            {
                "data": "2026-08-30",
                "fiis": [
                    {"DIVIDEND YIELD": 0.01, "P/VP": 0.8, "score": 70},
                    {"DIVIDEND YIELD": 0.02, "P/VP": 1.0, "score": 80},
                ],
                "acoes": [{"score": 75}, {"score": 85}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "2026-08-31.json").write_text(
        json.dumps(
            {
                "data": "2026-08-31",
                "kpis": {
                    "dy_medio_fiis_carteira": 0.012,
                    "pvp_medio_fiis_carteira": 0.72,
                    "score_medio_fiis_carteira": 69.8,
                    "score_medio_acoes_carteira": 74.2,
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "index.json").write_text("[]", encoding="utf-8")

    rows = rebuild_dashboard_kpi_history(str(tmp_path))

    assert [row["data"] for row in rows] == ["2026-08-30", "2026-08-31"]
    assert rows[0] == {
        "data": "2026-08-30",
        "dyFiis": 0.015,
        "pvpFiis": 0.9,
        "scoreFiis": 75.0,
        "scoreAcoes": 80.0,
    }
    assert rows[1]["scoreAcoes"] == 74.2

    payload = json.loads((tmp_path / "kpi-history.json").read_text(encoding="utf-8"))
    assert payload == {"version": 1, "items": rows}

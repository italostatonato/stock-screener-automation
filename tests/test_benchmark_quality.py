import pandas as pd

from src import benchmark


def test_get_benchmarks_omits_single_point_yahoo_series(monkeypatch):
    one_point = pd.DataFrame({
        "data": pd.to_datetime(["2026-08-28"]),
        "valor": [123.45],
    })
    two_points = pd.DataFrame({
        "data": pd.to_datetime(["2026-08-27", "2026-08-28"]),
        "valor": [100.0, 101.0],
    })

    monkeypatch.setattr(
        benchmark,
        "_fetch_yahoo",
        lambda ticker, nome, meses: one_point if nome == "IMOB" else two_points,
    )
    monkeypatch.setattr(
        benchmark,
        "_fetch_bcb",
        lambda codigo, meses: pd.DataFrame(columns=["data", "valor"]),
    )

    result = benchmark.get_benchmarks()

    assert result["IMOB"].empty
    assert len(result["IBOV"]) == 2

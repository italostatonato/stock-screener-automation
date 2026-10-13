import pandas as pd
import pytest
import requests
from types import SimpleNamespace

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


def test_fetch_bcb_recovers_after_temporary_failures(monkeypatch):
    calls = []
    delays = []
    failures = [
        requests.Timeout("BCB demorou"),
        requests.HTTPError("503", response=SimpleNamespace(status_code=503)),
    ]

    def get(url, timeout):
        calls.append((url, timeout))
        if failures:
            raise failures.pop(0)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: [
                {"data": "09/10/2026", "valor": "0.050788"},
                {"data": "08/10/2026", "valor": "0.050788"},
            ],
        )

    monkeypatch.setattr(benchmark.requests, "get", get)
    monkeypatch.setattr(benchmark, "sleep", delays.append)

    result = benchmark._fetch_bcb(12)

    assert len(calls) == 3
    assert len({url for url, _ in calls}) == 1
    assert "&dataFinal=" in calls[0][0]
    assert all(timeout == 15 for _, timeout in calls)
    assert delays == [1, 2]
    assert result["data"].dt.strftime("%Y-%m-%d").tolist() == ["2026-10-08", "2026-10-09"]
    assert result["valor"].tolist() == pytest.approx([0.050788, 0.050788])


@pytest.mark.parametrize("status,attempts,delays", [(400, 1, []), (429, 3, [1, 2]), (502, 3, [1, 2])])
def test_fetch_bcb_limits_retries_and_leaves_missing_data_explicit(monkeypatch, status, attempts, delays):
    calls = []
    observed_delays = []

    def get(url, timeout):
        calls.append(url)
        raise requests.HTTPError(str(status), response=SimpleNamespace(status_code=status))

    monkeypatch.setattr(benchmark.requests, "get", get)
    monkeypatch.setattr(benchmark, "sleep", observed_delays.append)

    result = benchmark._fetch_bcb(12)

    assert result.empty
    assert len(calls) == attempts
    assert observed_delays == delays

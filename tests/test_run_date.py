from datetime import datetime, timezone

from main import current_run_date


def test_current_run_date_uses_sao_paulo_timezone():
    instant = datetime(2026, 8, 31, 0, 7, tzinfo=timezone.utc)

    assert current_run_date(instant) == "2026-08-30"

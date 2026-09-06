"""Run the financial calculator's JavaScript tests as part of pytest/CI."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_dashboard_hybrid_javascript():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the dashboard JavaScript tests")
    result = subprocess.run(
        [node, "--test", "tests/hybrid_portfolio.test.cjs"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr

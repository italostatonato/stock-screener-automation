import json
from datetime import date

import pytest

from scripts.dashboard_release import ORIGINS, collection_required, latest_snapshot, publication_errors, snapshot_digest


def test_scheduled_recovery_reuses_a_snapshot_from_the_same_week():
    monday = date(2026, 11, 9)
    tuesday = date(2026, 11, 10)
    previous = date(2026, 11, 2)
    assert collection_required("schedule", monday, previous)
    assert collection_required("schedule", tuesday, None)
    assert not collection_required("schedule", tuesday, monday)
    assert collection_required("workflow_dispatch", monday, monday)


def test_latest_snapshot_rejects_partial_ranking(tmp_path):
    day = "2026-11-09"
    (tmp_path / "index.json").write_text(json.dumps([day]), encoding="utf-8")
    (tmp_path / f"{day}.json").write_text(
        json.dumps({"data": day, "acoes": [{"ticker": "TEST3"}], "fiis": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="sem ranking de fiis"):
        latest_snapshot(tmp_path)


def test_publication_requires_the_new_revision_and_data_on_both_origins():
    day = "2026-11-09"
    payload = {"data": day, "acoes": [{"ticker": "TEST3"}], "fiis": [{"ticker": "TEST11"}]}
    expected = {"commit": "b" * 40, "snapshot": day, "snapshot_sha256": snapshot_digest(payload)}
    public = {
        f"{origin}/data/{filename}": value
        for origin in ORIGINS
        for filename, value in (
            ("publication.json", expected),
            ("index.json", [day, "2026-11-02"]),
            (f"{day}.json", payload),
        )
    }
    assert publication_errors(expected, public.__getitem__) == []

    pages, mirror = ORIGINS
    public[f"{pages}/data/publication.json"] = {**expected, "commit": "a" * 40}
    public[f"{mirror}/data/index.json"] = ["2026-11-02"]
    errors = publication_errors(expected, public.__getitem__)
    assert len(errors) == 2
    assert "revisão esperada" in errors[0]
    assert "índice ainda aponta para 2026-11-02" in errors[1]

    public[f"{pages}/data/publication.json"] = expected
    public[f"{mirror}/data/index.json"] = [day]
    public[f"{mirror}/data/{day}.json"] = {**payload, "acoes": [{"ticker": "OLD3"}]}
    errors = publication_errors(expected, public.__getitem__)
    assert len(errors) == 1
    assert mirror in errors[0] and "diverge do arquivo local" in errors[0]

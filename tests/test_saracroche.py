import json
from pathlib import Path

import pytest

from ovh_spam_filter import saracroche


FIXTURE = {
    "version": "2026-05-20T01:00:53+00:00",
    "name": "Test list",
    "license": "GPL-3.0",
    "description": "fixture",
    "blocked_numbers_count": 4,
    "patterns": [
        {"name": "Préfixe démarchage ARCEP", "action": "block", "pattern": "33270######"},
        {"name": "Préfixe démarchage ARCEP", "action": "block", "pattern": "33377######"},
        {"name": "Spam potentiel : W3tel", "action": "identify", "pattern": "3397837####"},
        {"name": "Préfixe démarchage ARCEP", "action": "block", "pattern": "33424######"},
    ],
}


def test_snapshot_filters_block_only() -> None:
    snap = saracroche._snapshot_from_payload(FIXTURE)
    patterns = snap.block_patterns()
    assert len(patterns) == 3
    assert all(p.raw.startswith("33") for p in patterns)
    assert all(p.name.startswith("Préfixe démarchage ARCEP") for p in patterns)


def test_snapshot_metadata() -> None:
    snap = saracroche._snapshot_from_payload(FIXTURE)
    assert snap.version == "2026-05-20T01:00:53+00:00"
    assert snap.name == "Test list"
    assert snap.total_patterns == 4


def test_write_and_read_cache_roundtrip(tmp_path: Path) -> None:
    snap = saracroche._snapshot_from_payload(FIXTURE)
    cache = tmp_path / "snap.json"
    saracroche.write_cache(snap, cache)
    assert cache.exists()
    reloaded = saracroche.read_cache(cache)
    assert reloaded.version == snap.version
    assert reloaded.total_patterns == snap.total_patterns
    assert [p.raw for p in reloaded.block_patterns()] == [p.raw for p in snap.block_patterns()]


def test_read_cache_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(saracroche.FetchError):
        saracroche.read_cache(tmp_path / "nope.json")


def test_read_cache_raises_when_malformed(tmp_path: Path) -> None:
    cache = tmp_path / "bad.json"
    cache.write_text("{not json", encoding="utf-8")
    with pytest.raises(saracroche.FetchError):
        saracroche.read_cache(cache)

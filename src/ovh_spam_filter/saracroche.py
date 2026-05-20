"""Client for the Saracroche community blocklist API.

Endpoint: GET https://saracroche.org/api/v1/lists/french-list-arcep-operators
Auth:     none
Schema:   { version, name, license, description, blocked_numbers_count,
            patterns: [{name, pattern, action}] }

Source cascade (see load_block_patterns):
  1. Live API
  2. Local cache file (last successful snapshot)
  3. Caller decides what to do with the FetchError (CLI falls back to ARCEP)
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ovh_spam_filter.patterns import BlockPattern

API_URL = "https://saracroche.org/api/v1/lists/french-list-arcep-operators"
DEFAULT_TIMEOUT_SECONDS = 15


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class SaracrocheSnapshot:
    version: str
    name: str
    total_patterns: int
    raw: dict[str, Any]

    def block_patterns(self) -> list[BlockPattern]:
        out: list[BlockPattern] = []
        for entry in self.raw.get("patterns", []):
            if entry.get("action") != "block":
                continue
            pattern = entry.get("pattern")
            name = entry.get("name")
            if not pattern or not name:
                continue
            out.append(BlockPattern(name=name, raw=pattern))
        return out


def fetch_from_api(timeout: float = DEFAULT_TIMEOUT_SECONDS) -> SaracrocheSnapshot:
    req = urllib.request.Request(
        API_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "ovh-voip-spam-filter/0.1 (+https://saracroche.org)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise FetchError(f"Saracroche API unreachable: {exc}") from exc

    return _snapshot_from_payload(payload)


def write_cache(snapshot: SaracrocheSnapshot, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(snapshot.raw, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_cache(cache_path: Path) -> SaracrocheSnapshot:
    if not cache_path.exists():
        raise FetchError(f"No cache at {cache_path}")
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FetchError(f"Cache unreadable: {exc}") from exc
    return _snapshot_from_payload(payload)


def cache_age_seconds(cache_path: Path) -> float | None:
    if not cache_path.exists():
        return None
    return time.time() - cache_path.stat().st_mtime


def _snapshot_from_payload(payload: dict[str, Any]) -> SaracrocheSnapshot:
    return SaracrocheSnapshot(
        version=payload.get("version", "unknown"),
        name=payload.get("name", "unknown"),
        total_patterns=len(payload.get("patterns", []) or []),
        raw=payload,
    )

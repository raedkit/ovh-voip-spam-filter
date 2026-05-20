"""Command-line interface for the OVH VoIP spam-filter blocklist generator."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from ovh_spam_filter import arcep, compact, saracroche
from ovh_spam_filter.ovh_csv import write_ovh_csv
from ovh_spam_filter.patterns import (
    BlockPattern,
    deduplicate_ovh_prefixes,
    prioritize,
)

DEFAULT_OUTPUT = Path("output/blocklist-ovh.csv")
DEFAULT_CACHE = Path("cache/saracroche-latest.json")

REPORTED_NUMBERS = [
    "+33270502261",
    "+33424283137",
    "+33270502265",
    "+33377113081",
    "+33377114132",
    "+33377493151",
]

SourceUsed = Literal["api", "cache", "arcep-hardcoded"]


@dataclass
class LoadResult:
    patterns: list[BlockPattern]
    source: SourceUsed
    snapshot: saracroche.SaracrocheSnapshot | None
    cache_age_seconds: float | None


def _load_patterns(cache_path: Path, offline: bool) -> LoadResult:
    if not offline:
        try:
            snap = saracroche.fetch_from_api()
            saracroche.write_cache(snap, cache_path)
            return LoadResult(
                patterns=snap.block_patterns(),
                source="api",
                snapshot=snap,
                cache_age_seconds=0.0,
            )
        except saracroche.FetchError as exc:
            print(f"  ! Saracroche API unreachable ({exc}). Falling back to cache.", file=sys.stderr)

    try:
        snap = saracroche.read_cache(cache_path)
        return LoadResult(
            patterns=snap.block_patterns(),
            source="cache",
            snapshot=snap,
            cache_age_seconds=saracroche.cache_age_seconds(cache_path),
        )
    except saracroche.FetchError as exc:
        print(f"  ! Cache unavailable ({exc}). Falling back to hard-coded ARCEP prefixes.", file=sys.stderr)

    return LoadResult(
        patterns=arcep.arcep_fallback_patterns(),
        source="arcep-hardcoded",
        snapshot=None,
        cache_age_seconds=None,
    )


def _check_coverage(prefixes: list[str], numbers: list[str]) -> list[tuple[str, str | None]]:
    results: list[tuple[str, str | None]] = []
    for num in numbers:
        normalized = num.lstrip("+")
        match = next(
            (p for p in prefixes if normalized.startswith(p.lstrip("+"))),
            None,
        )
        results.append((num, match))
    return results


def _format_age(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}min"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _parse_compact_flag(value: str):
    if value == "none":
        return None
    if value == "safe":
        return compact.compact_safe
    if value.startswith("lossy:"):
        threshold = int(value.split(":", 1)[1])
        return lambda prefixes: compact.compact_lossy(prefixes, threshold=threshold)
    raise SystemExit(f"Unknown --compact value: {value!r} (expected none|safe|lossy:N)")


def cmd_generate(args: argparse.Namespace) -> int:
    cache_path = Path(args.cache)
    output_path = Path(args.output)

    print(f"Loading patterns (offline={args.offline})...")
    result = _load_patterns(cache_path, offline=args.offline)

    if result.source == "api":
        snap = result.snapshot
        assert snap is not None
        print(
            f"  OK from API: version {snap.version}, "
            f"{snap.total_patterns} patterns total, "
            f"{len(result.patterns)} block-only"
        )
    elif result.source == "cache":
        snap = result.snapshot
        assert snap is not None
        print(
            f"  OK from CACHE (age {_format_age(result.cache_age_seconds)}): "
            f"version {snap.version}, {len(result.patterns)} block-only"
        )
    else:
        print(f"  OK from HARD-CODED ARCEP: {len(result.patterns)} prefixes (degraded mode)")

    ordered = prioritize(result.patterns)
    raw_prefixes = [p.to_ovh_prefix() for p in ordered]
    prefixes = deduplicate_ovh_prefixes(raw_prefixes)

    if len(raw_prefixes) != len(prefixes):
        print(f"  Deduplicated {len(raw_prefixes) - len(prefixes)} redundant subprefixes")

    compaction = _parse_compact_flag(args.compact)
    if compaction is not None:
        before = len(prefixes)
        prefixes = compaction(prefixes)
        # Compaction can introduce new subsumption (a parent merge may make a
        # longer sibling redundant), so dedup again.
        prefixes = deduplicate_ovh_prefixes(prefixes)
        if len(prefixes) < before:
            print(f"  Compacted {before} -> {len(prefixes)} ({args.compact})")

    if args.max_entries is not None and len(prefixes) > args.max_entries:
        print(f"  Truncating {len(prefixes)} -> {args.max_entries} (ARCEP entries protected by ordering)")
        prefixes = prefixes[: args.max_entries]

    write_ovh_csv(prefixes, output_path)
    print(f"Wrote {output_path} ({len(prefixes)} entries)")

    coverage = _check_coverage(prefixes, REPORTED_NUMBERS)
    covered = sum(1 for _, m in coverage if m is not None)
    print(f"\nReported-numbers coverage check: {covered}/{len(REPORTED_NUMBERS)}")
    for num, match in coverage:
        flag = "OK" if match else "MISSING"
        suffix = f" by {match}" if match else ""
        print(f"  {flag}  {num}{suffix}")

    return 0 if covered == len(REPORTED_NUMBERS) else 1


def cmd_status(args: argparse.Namespace) -> int:
    cache_path = Path(args.cache)

    print(f"Cache file: {cache_path}")
    age = saracroche.cache_age_seconds(cache_path)
    if age is None:
        print("  Status: ABSENT")
    else:
        cached = saracroche.read_cache(cache_path)
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
        print(f"  Status: present, modified {mtime} ({_format_age(age)} ago)")
        print(f"  Version: {cached.version}")
        print(f"  Name: {cached.name}")
        print(f"  Total patterns: {cached.total_patterns}")
        print(f"  Block-only patterns: {len(cached.block_patterns())}")

    print(f"\nProbing Saracroche API ({saracroche.API_URL})...")
    try:
        snap = saracroche.fetch_from_api(timeout=10)
        print(f"  OK: version {snap.version}, {snap.total_patterns} patterns")
        if age is not None and cached.version != snap.version:
            print("  ! Cache is stale -- run `generate` to refresh")
    except saracroche.FetchError as exc:
        print(f"  FAIL: {exc}")
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ovh-spam-filter",
        description="Generate an OVH VoIP blocklist CSV from the Saracroche community list.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Fetch Saracroche and write the OVH CSV")
    p_gen.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV path")
    p_gen.add_argument("--cache", default=str(DEFAULT_CACHE), help="Cache JSON path")
    p_gen.add_argument("--max-entries", type=int, default=None, help="Truncate to N rows (ARCEP first)")
    p_gen.add_argument("--offline", action="store_true", help="Skip network, use cache or ARCEP fallback")
    p_gen.add_argument(
        "--compact",
        default="none",
        help="Compaction strategy: none | safe | lossy:N (N in [2,10], 10 == safe)",
    )
    p_gen.set_defaults(func=cmd_generate)

    p_status = sub.add_parser("status", help="Inspect cache freshness and API reachability")
    p_status.add_argument("--cache", default=str(DEFAULT_CACHE), help="Cache JSON path")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)

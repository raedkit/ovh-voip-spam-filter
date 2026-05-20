"""Command-line interface for the OVH VoIP spam-filter blocklist generator.

Subcommands:
  generate  Phase 1 — write the OVH CSV (file cache supported, for manual import).
  status    Phase 1 — inspect Saracroche cache freshness and API reachability.
  discover  Phase 2 — list OVH billing accounts and screen-capable lines.
  sync      Phase 2 — reconcile OVH blacklist with Saracroche (push API, throttled).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ovh_voip_spam_filter import arcep, config, logging_setup, ovh_api, reconcile, saracroche
from ovh_voip_spam_filter.ovh_csv import write_ovh_csv
from ovh_voip_spam_filter.patterns import (
    BlockPattern,
    deduplicate_ovh_prefixes,
    prioritize,
)

logger = logging_setup.get(__name__)

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


# ============================================================================
# Phase 1 commands (CSV-based, kept unchanged)
# ============================================================================


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
            print(
                f"  ! Saracroche API unreachable ({exc}). Falling back to cache.", file=sys.stderr
            )

    try:
        snap = saracroche.read_cache(cache_path)
        return LoadResult(
            patterns=snap.block_patterns(),
            source="cache",
            snapshot=snap,
            cache_age_seconds=saracroche.cache_age_seconds(cache_path),
        )
    except saracroche.FetchError as exc:
        print(
            f"  ! Cache unavailable ({exc}). Falling back to hard-coded ARCEP prefixes.",
            file=sys.stderr,
        )

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

    if args.max_entries is not None and len(prefixes) > args.max_entries:
        print(
            f"  Truncating {len(prefixes)} -> {args.max_entries} (ARCEP entries protected by ordering)"
        )
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
    cached: saracroche.SaracrocheSnapshot | None = None
    if age is None:
        print("  Status: ABSENT")
    else:
        cached = saracroche.read_cache(cache_path)
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=UTC).isoformat(
            timespec="seconds"
        )
        print(f"  Status: present, modified {mtime} ({_format_age(age)} ago)")
        print(f"  Version: {cached.version}")
        print(f"  Name: {cached.name}")
        print(f"  Total patterns: {cached.total_patterns}")
        print(f"  Block-only patterns: {len(cached.block_patterns())}")

    print(f"\nProbing Saracroche API ({saracroche.API_URL})...")
    try:
        snap = saracroche.fetch_from_api(timeout=10)
        print(f"  OK: version {snap.version}, {snap.total_patterns} patterns")
        if cached is not None and cached.version != snap.version:
            print("  ! Cache is stale -- run `generate` to refresh")
    except saracroche.FetchError as exc:
        print(f"  FAIL: {exc}")
        return 2
    return 0


# ============================================================================
# Phase 2 commands (API push, K8s-target)
# ============================================================================


def _build_client(cfg: config.AppConfig) -> ovh_api.OvhClient:
    creds = config.require_signed_credentials(cfg)
    return ovh_api.OvhClient(
        credentials=creds,
        min_interval_seconds=cfg.rate_limit_ms / 1000.0,
    )


def cmd_discover(args: argparse.Namespace) -> int:
    cfg = config.load()
    logging_setup.setup(cfg.log_level)
    client = _build_client(cfg)

    try:
        client.whoami()
    except ovh_api.OvhApiError as exc:
        logger.error("Credentials check failed: %s", exc)
        return 1

    billing_accounts = client.list_billing_accounts()
    if not billing_accounts:
        logger.warning("No telephony billing accounts visible with these credentials")
        return 0

    print(f"Found {len(billing_accounts)} billing account(s):")
    for ba in billing_accounts:
        print(f"\n  billing_account = {ba}")
        try:
            services = client.list_screen_services(ba)
        except ovh_api.OvhApiError as exc:
            print(f"    (failed to list screen services: {exc})")
            continue
        if not services:
            print("    (no screen-capable services)")
            continue
        for sn in services:
            print(f"    service_name    = {sn}")
    print(
        "\nCopy the chosen pair into env:"
        "\n  OVH_BILLING_ACCOUNT=<billing_account>"
        "\n  OVH_SERVICE_NAME=<service_name>"
    )
    return 0


def cmd_sync(args: argparse.Namespace) -> int:  # noqa: PLR0911
    cfg = config.load()
    logging_setup.setup(cfg.log_level)

    if args.rate_limit_ms is not None:
        cfg = _override_rate_limit(cfg, args.rate_limit_ms)

    try:
        billing_account, service_name = config.require_target(cfg)
    except config.ConfigError as exc:
        logger.error("%s", exc)
        return 1

    target = reconcile.load_target()
    target_prefixes = reconcile.target_to_prefixes(target)
    logger.info(
        "Target: %d prefixes (mode=%s)",
        len(target_prefixes),
        target.mode.value,
    )

    client = _build_client(cfg)
    try:
        me = client.whoami()
        logger.info("Authenticated as nichandle=%s", me.get("nichandle", "?"))
    except ovh_api.OvhApiError as exc:
        logger.error("Auth check failed (%s) — aborting", exc)
        return 1

    try:
        reconcile.ensure_blacklist_enabled(client, billing_account, service_name)
    except ovh_api.OvhApiError as exc:
        logger.error("Failed to set screen state to blacklist: %s — aborting", exc)
        return 1

    try:
        current = reconcile.load_current(client, billing_account, service_name)
    except ovh_api.OvhApiError as exc:
        logger.error("Failed to read current screenLists: %s — aborting", exc)
        return 1

    plan = reconcile.compute_plan(target.mode, target_prefixes, current)
    logger.info("Plan: %s", reconcile.summarize_plan(plan, cfg.rate_limit_ms))

    if args.dry_run:
        _print_plan_preview(plan)
        logger.info("Dry-run only — no changes applied")
        return 0

    if not plan.to_add and not plan.to_remove:
        logger.info("Already in sync, nothing to do (idempotent run)")
        return 0

    result = reconcile.apply_plan(client, billing_account, service_name, plan)
    logger.info(
        "Sync complete: added=%d removed=%d failed=%d duration=%.1fs throttle_adapts=%d",
        result.added,
        result.removed,
        result.failed,
        result.duration_seconds,
        result.throttle_adaptations,
    )
    if result.failed:
        logger.warning("%d operation(s) failed; next run will retry (idempotent)", result.failed)
    return 0


def _override_rate_limit(cfg: config.AppConfig, rate_limit_ms: int) -> config.AppConfig:
    return config.AppConfig(
        credentials=cfg.credentials,
        billing_account=cfg.billing_account,
        service_name=cfg.service_name,
        rate_limit_ms=rate_limit_ms,
        log_level=cfg.log_level,
    )


def _print_plan_preview(plan: reconcile.ReconcilePlan) -> None:
    print(f"\nReconcile plan (mode={plan.mode.value}):")
    print(f"  to add    ({len(plan.to_add)} entries):")
    for p in plan.to_add[:10]:
        print(f"    + {p}")
    if len(plan.to_add) > 10:
        print(f"    ... and {len(plan.to_add) - 10} more")
    print(f"  to remove ({len(plan.to_remove)} entries):")
    for e in plan.to_remove[:10]:
        print(f"    - id={e.id} {e.call_number}")
    if len(plan.to_remove) > 10:
        print(f"    ... and {len(plan.to_remove) - 10} more")


# ============================================================================
# Entry point
# ============================================================================


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ovh-voip-spam-filter",
        description="Reconcile your OVH SIP blacklist with the Saracroche community list.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Write the OVH CSV (Phase 1, manual import)")
    p_gen.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV path")
    p_gen.add_argument("--cache", default=str(DEFAULT_CACHE), help="Cache JSON path")
    p_gen.add_argument(
        "--max-entries", type=int, default=None, help="Truncate to N rows (ARCEP first)"
    )
    p_gen.add_argument(
        "--offline", action="store_true", help="Skip network, use cache or ARCEP fallback"
    )
    p_gen.set_defaults(func=cmd_generate)

    p_status = sub.add_parser("status", help="Inspect cache freshness and API reachability")
    p_status.add_argument("--cache", default=str(DEFAULT_CACHE), help="Cache JSON path")
    p_status.set_defaults(func=cmd_status)

    p_discover = sub.add_parser(
        "discover", help="List OVH billing accounts and screen-capable lines"
    )
    p_discover.set_defaults(func=cmd_discover)

    p_sync = sub.add_parser(
        "sync",
        help="Reconcile OVH blacklist with Saracroche (strict in normal mode, additive in degraded)",
    )
    p_sync.add_argument("--dry-run", action="store_true", help="Show the plan without applying it")
    p_sync.add_argument(
        "--rate-limit-ms",
        type=int,
        default=None,
        help="Min ms between API calls (default from RATE_LIMIT_MS env or 1000)",
    )
    p_sync.set_defaults(func=cmd_sync)

    args = parser.parse_args(argv)
    return int(args.func(args))

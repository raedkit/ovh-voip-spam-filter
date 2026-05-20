"""Reconciliation pipeline: OVH state ← target patterns (Saracroche or ARCEP fallback).

Two modes, determined at runtime by Saracroche reachability:

  Normal mode  (Saracroche fetched OK):
    Saracroche is the source of truth.
    to_add    = target  - current   (POST)
    to_remove = current - target    (DELETE)
    Strict sync.

  Degraded mode  (Saracroche unreachable):
    Fall back to hard-coded ARCEP prefixes (23 entries, 100% démarchage légal FR).
    to_add    = arcep - current     (POST)
    to_remove = []                  (NEVER delete — partial knowledge could regress)
    Additive-only.

The dry-run variant returns the plan without applying it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum

from ovh_voip_spam_filter import arcep, saracroche
from ovh_voip_spam_filter.logging_setup import get as _get_logger
from ovh_voip_spam_filter.ovh_api import OvhApiError, OvhClient
from ovh_voip_spam_filter.patterns import (
    BlockPattern,
    deduplicate_ovh_prefixes,
    prioritize,
)

logger = _get_logger(__name__)


class SyncMode(StrEnum):
    NORMAL = "normal"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class TargetState:
    mode: SyncMode
    patterns: list[BlockPattern]
    saracroche_version: str | None


@dataclass(frozen=True)
class CurrentEntry:
    """An existing screenList entry on OVH side."""

    id: int
    call_number: str
    nature: str
    type: str


@dataclass(frozen=True)
class ReconcilePlan:
    mode: SyncMode
    target_prefixes: list[str]
    current_entries: list[CurrentEntry]
    to_add: list[str]
    to_remove: list[CurrentEntry]


@dataclass
class ReconcileResult:
    mode: SyncMode
    added: int = 0
    removed: int = 0
    failed: int = 0
    duration_seconds: float = 0.0
    throttle_adaptations: int = 0
    errors: list[str] = field(default_factory=list)


def load_target() -> TargetState:
    """Saracroche live → fallback to hard-coded ARCEP. Cache is not used here.

    The Phase-1 file cache is bypassed in K8s/cron context: container is
    ephemeral, Saracroche is cheap to refetch (~150 KB JSON). The CLI mode
    (Phase 1) still has its own cached path via `generate`.
    """
    try:
        snap = saracroche.fetch_from_api()
        patterns = snap.block_patterns()
        logger.info(
            "Saracroche live: version=%s, %d patterns total, %d block-only",
            snap.version,
            snap.total_patterns,
            len(patterns),
        )
        return TargetState(mode=SyncMode.NORMAL, patterns=patterns, saracroche_version=snap.version)
    except saracroche.FetchError as exc:
        logger.warning(
            "Saracroche unreachable (%s) — degraded mode with hard-coded ARCEP",
            exc,
        )
        return TargetState(
            mode=SyncMode.DEGRADED,
            patterns=arcep.arcep_fallback_patterns(),
            saracroche_version=None,
        )


def target_to_prefixes(target: TargetState) -> list[str]:
    ordered = prioritize(target.patterns)
    raw = [p.to_ovh_prefix() for p in ordered]
    return deduplicate_ovh_prefixes(raw)


def load_current(client: OvhClient, billing_account: str, service_name: str) -> list[CurrentEntry]:
    """Read every existing screenList entry. N + 1 GETs (throttled by client)."""
    ids = client.list_screen_list_ids(billing_account, service_name)
    logger.info("OVH has %d existing screenList entries; fetching details", len(ids))
    out: list[CurrentEntry] = []
    for entry_id in ids:
        d = client.get_screen_list_entry(billing_account, service_name, entry_id)
        out.append(
            CurrentEntry(
                id=int(d.get("id", entry_id)),
                call_number=str(d.get("callNumber", "")),
                nature=str(d.get("nature", "")),
                type=str(d.get("type", "")),
            )
        )
    return out


def compute_plan(
    mode: SyncMode,
    target_prefixes: list[str],
    current: list[CurrentEntry],
) -> ReconcilePlan:
    target_set = set(target_prefixes)
    current_blacklist = [e for e in current if e.type == "incomingBlackList"]
    current_set = {e.call_number for e in current_blacklist}

    to_add = [p for p in target_prefixes if p not in current_set]

    if mode is SyncMode.NORMAL:
        to_remove = [e for e in current_blacklist if e.call_number not in target_set]
    else:
        to_remove = []  # additive-only in degraded mode (anti-regression)

    return ReconcilePlan(
        mode=mode,
        target_prefixes=target_prefixes,
        current_entries=current,
        to_add=to_add,
        to_remove=to_remove,
    )


def ensure_blacklist_enabled(client: OvhClient, billing_account: str, service_name: str) -> None:
    """If incomingScreenList is 'disabled', PUT it to 'blacklist' preserving outgoing.

    Per design (validated with user): auto-activate, never block, WARN log.
    """
    state = client.get_screen_state(billing_account, service_name)
    incoming = state.get("incomingScreenList")
    outgoing = state.get("outgoingScreenList")
    if incoming == "blacklist":
        logger.info("Screen state: incoming=blacklist (already enabled)")
        return
    logger.warning(
        "Screen state: incoming=%s outgoing=%s — auto-activating incoming=blacklist "
        "(preserving outgoing=%s)",
        incoming,
        outgoing,
        outgoing,
    )
    client.set_screen_state(
        billing_account,
        service_name,
        incoming="blacklist",
        outgoing=outgoing,
    )


def apply_plan(
    client: OvhClient,
    billing_account: str,
    service_name: str,
    plan: ReconcilePlan,
) -> ReconcileResult:
    started = time.monotonic()
    result = ReconcileResult(mode=plan.mode)

    total_add = len(plan.to_add)
    for i, call_number in enumerate(plan.to_add, start=1):
        try:
            client.add_screen_list_entry(
                billing_account,
                service_name,
                call_number=call_number,
            )
            result.added += 1
            logger.info("Added %s (%d/%d)", call_number, i, total_add)
        except OvhApiError as exc:
            result.failed += 1
            result.errors.append(f"POST {call_number}: {exc}")
            logger.error("POST %s failed (%d/%d): %s", call_number, i, total_add, exc)

    total_remove = len(plan.to_remove)
    for i, entry in enumerate(plan.to_remove, start=1):
        try:
            client.delete_screen_list_entry(billing_account, service_name, entry.id)
            result.removed += 1
            logger.info(
                "Removed id=%d callNumber=%s (%d/%d)",
                entry.id,
                entry.call_number,
                i,
                total_remove,
            )
        except OvhApiError as exc:
            result.failed += 1
            result.errors.append(f"DELETE id={entry.id}: {exc}")
            logger.error(
                "DELETE id=%d failed (%d/%d): %s",
                entry.id,
                i,
                total_remove,
                exc,
            )

    result.duration_seconds = time.monotonic() - started
    result.throttle_adaptations = client.total_throttle_adaptations
    return result


def summarize_plan(plan: ReconcilePlan, rate_limit_ms: int) -> str:
    """Human-readable summary of the plan (for dry-run output)."""
    n_ops = len(plan.to_add) + len(plan.to_remove)
    estimated_seconds = n_ops * (rate_limit_ms / 1000.0)
    return (
        f"mode={plan.mode.value} "
        f"target={len(plan.target_prefixes)} prefixes  "
        f"existing={len(plan.current_entries)} entries  "
        f"to_add={len(plan.to_add)}  "
        f"to_remove={len(plan.to_remove)}  "
        f"~estimated_duration={estimated_seconds:.0f}s"
    )

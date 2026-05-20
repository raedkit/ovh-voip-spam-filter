"""Reconcile pipeline tests with a fake OvhClient.

Critical invariant tested explicitly: in degraded mode, **no DELETE is emitted**
no matter what's currently on OVH (anti-regression).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

from ovh_spam_filter import arcep, reconcile, saracroche
from ovh_spam_filter.patterns import BlockPattern
from ovh_spam_filter.reconcile import CurrentEntry, SyncMode


# ---------- fake client ----------


@dataclass
class _FakeClient:
    """Records calls; returns canned state."""
    existing: list[CurrentEntry] = field(default_factory=list)
    screen_state: dict[str, str] = field(default_factory=lambda: {"incomingScreenList": "blacklist"})
    added: list[str] = field(default_factory=list)
    removed: list[int] = field(default_factory=list)
    screen_state_writes: list[dict[str, Any]] = field(default_factory=list)
    total_throttle_adaptations: int = 0

    def whoami(self):
        return {"nichandle": "abc-ovh"}

    def list_screen_list_ids(self, ba, sn):
        return [e.id for e in self.existing]

    def get_screen_list_entry(self, ba, sn, entry_id):
        for e in self.existing:
            if e.id == entry_id:
                return {"id": e.id, "callNumber": e.call_number, "nature": e.nature, "type": e.type}
        return {}

    def add_screen_list_entry(self, ba, sn, *, call_number, nature="international", type_="incomingBlackList"):
        self.added.append(call_number)

    def delete_screen_list_entry(self, ba, sn, entry_id):
        self.removed.append(entry_id)

    def get_screen_state(self, ba, sn):
        return dict(self.screen_state)

    def set_screen_state(self, ba, sn, *, incoming=None, outgoing=None):
        self.screen_state_writes.append({"incoming": incoming, "outgoing": outgoing})
        if incoming is not None:
            self.screen_state["incomingScreenList"] = incoming
        if outgoing is not None:
            self.screen_state["outgoingScreenList"] = outgoing


# ---------- normal mode: strict sync ----------


def test_normal_mode_adds_missing_and_removes_disappeared() -> None:
    plan = reconcile.compute_plan(
        SyncMode.NORMAL,
        target_prefixes=["+33162", "+33270", "+33377"],
        current=[
            CurrentEntry(id=1, call_number="+33162", nature="international", type="incomingBlackList"),
            CurrentEntry(id=2, call_number="+33999", nature="international", type="incomingBlackList"),
        ],
    )
    assert plan.to_add == ["+33270", "+33377"]
    assert [e.id for e in plan.to_remove] == [2]


def test_normal_mode_idempotent_when_in_sync() -> None:
    plan = reconcile.compute_plan(
        SyncMode.NORMAL,
        target_prefixes=["+33162", "+33270"],
        current=[
            CurrentEntry(id=1, call_number="+33162", nature="international", type="incomingBlackList"),
            CurrentEntry(id=2, call_number="+33270", nature="international", type="incomingBlackList"),
        ],
    )
    assert plan.to_add == []
    assert plan.to_remove == []


def test_normal_mode_ignores_whitelist_and_other_types() -> None:
    """Only incomingBlackList entries are considered for the diff."""
    plan = reconcile.compute_plan(
        SyncMode.NORMAL,
        target_prefixes=["+33162"],
        current=[
            CurrentEntry(id=1, call_number="+33999", nature="international", type="incomingWhiteList"),
            CurrentEntry(id=2, call_number="+33888", nature="international", type="outgoingBlackList"),
        ],
    )
    # No incomingBlackList present → just add target, never touch the others
    assert plan.to_add == ["+33162"]
    assert plan.to_remove == []


# ---------- degraded mode: additive only ----------


def test_degraded_mode_never_removes_even_if_extras_exist() -> None:
    """The critical anti-regression test. If Saracroche is down and OVH has
    643 entries while ARCEP fallback has only 23, we must NOT delete the 620
    extras — partial knowledge could permanently truncate the user's blocklist.
    """
    arcep_prefixes = [p.to_ovh_prefix() for p in arcep.arcep_fallback_patterns()]
    existing = [
        CurrentEntry(id=i, call_number=cn, nature="international", type="incomingBlackList")
        for i, cn in enumerate(
            arcep_prefixes + ["+33189123", "+33449", "+33756"],  # extras from a richer Saracroche
            start=1,
        )
    ]
    plan = reconcile.compute_plan(
        SyncMode.DEGRADED,
        target_prefixes=arcep_prefixes,
        current=existing,
    )
    assert plan.to_add == []  # ARCEP already present
    assert plan.to_remove == []  # never delete in degraded


def test_degraded_mode_adds_missing_arcep_prefixes() -> None:
    arcep_prefixes = [p.to_ovh_prefix() for p in arcep.arcep_fallback_patterns()]
    # Suppose OVH has only the first 5 ARCEP entries
    existing = [
        CurrentEntry(id=i, call_number=cn, nature="international", type="incomingBlackList")
        for i, cn in enumerate(arcep_prefixes[:5], start=1)
    ]
    plan = reconcile.compute_plan(
        SyncMode.DEGRADED,
        target_prefixes=arcep_prefixes,
        current=existing,
    )
    assert plan.to_add == arcep_prefixes[5:]
    assert plan.to_remove == []


# ---------- ensure_blacklist_enabled ----------


def test_ensure_blacklist_enabled_noop_when_already_blacklist() -> None:
    client = _FakeClient(screen_state={"incomingScreenList": "blacklist", "outgoingScreenList": "disabled"})
    reconcile.ensure_blacklist_enabled(client, "ba", "sn")
    assert client.screen_state_writes == []


def test_ensure_blacklist_enabled_promotes_disabled_preserving_outgoing() -> None:
    client = _FakeClient(screen_state={"incomingScreenList": "disabled", "outgoingScreenList": "whitelist"})
    reconcile.ensure_blacklist_enabled(client, "ba", "sn")
    assert client.screen_state_writes == [{"incoming": "blacklist", "outgoing": "whitelist"}]
    assert client.screen_state["incomingScreenList"] == "blacklist"


# ---------- apply_plan ----------


def test_apply_plan_emits_expected_adds_and_removes() -> None:
    client = _FakeClient(existing=[
        CurrentEntry(id=99, call_number="+33999", nature="international", type="incomingBlackList"),
    ])
    plan = reconcile.ReconcilePlan(
        mode=SyncMode.NORMAL,
        target_prefixes=["+33162"],
        current_entries=client.existing,
        to_add=["+33162"],
        to_remove=client.existing,
    )
    result = reconcile.apply_plan(client, "ba", "sn", plan)
    assert client.added == ["+33162"]
    assert client.removed == [99]
    assert result.added == 1
    assert result.removed == 1


# ---------- load_target with mocked Saracroche ----------


def test_load_target_normal_when_saracroche_ok() -> None:
    fake_snap = saracroche.SaracrocheSnapshot(
        version="2026-05-20", name="t", total_patterns=2,
        raw={"patterns": [
            {"name": "Préfixe démarchage ARCEP", "action": "block", "pattern": "33162######"},
            {"name": "Spam W3tel", "action": "identify", "pattern": "3397837####"},
        ]},
    )
    with patch.object(saracroche, "fetch_from_api", return_value=fake_snap):
        target = reconcile.load_target()
    assert target.mode is SyncMode.NORMAL
    assert len(target.patterns) == 1  # block-only filter
    assert target.saracroche_version == "2026-05-20"


def test_load_target_degraded_when_saracroche_fails() -> None:
    with patch.object(saracroche, "fetch_from_api", side_effect=saracroche.FetchError("nope")):
        target = reconcile.load_target()
    assert target.mode is SyncMode.DEGRADED
    assert target.saracroche_version is None
    assert all(p.is_arcep for p in target.patterns)

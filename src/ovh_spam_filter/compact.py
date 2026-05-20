"""Prefix compaction strategies to shrink the OVH CSV.

Motivation: the OVH manager's CSV importer returns HTTP 429 (Too Many Requests)
on large lists. Reducing the row count reduces the per-second POST burst the
manager generates internally.

Two strategies:
  - safe: merge a sibling cluster only when ALL 10 children of a parent prefix
    are present. Strictly equivalent coverage, zero over-blocking.
  - lossy(N): merge as soon as N out of 10 children are present. Over-blocks
    by at most (10-N) ranges per merge, but can shrink the list drastically.
    Use with care.

Both operate on already-deduplicated prefix lists (see patterns.deduplicate_ovh_prefixes).
"""

from __future__ import annotations

from collections import defaultdict


def compact_safe(prefixes: list[str]) -> list[str]:
    """Repeatedly merge complete sibling clusters until fixed-point."""
    return _compact_until_stable(prefixes, threshold=10)


def compact_lossy(prefixes: list[str], threshold: int) -> list[str]:
    """Merge as soon as `threshold` siblings (out of 10) share a parent.

    `threshold` must be in [2, 10]. 10 is equivalent to compact_safe.
    """
    if not 2 <= threshold <= 10:
        raise ValueError(f"threshold must be in [2, 10], got {threshold}")
    return _compact_until_stable(prefixes, threshold=threshold)


def _compact_until_stable(prefixes: list[str], threshold: int) -> list[str]:
    current = prefixes
    while True:
        nxt = _compact_one_pass(current, threshold)
        if len(nxt) == len(current):
            return nxt
        current = nxt


def _compact_one_pass(prefixes: list[str], threshold: int) -> list[str]:
    children_by_parent: dict[str, set[str]] = defaultdict(set)
    for p in prefixes:
        if len(p) >= 2:  # need at least one char after the leading '+'
            children_by_parent[p[:-1]].add(p[-1])

    mergeable_parents = {
        parent
        for parent, kids in children_by_parent.items()
        if len(kids) >= threshold and parent.startswith("+") and len(parent) >= 2
    }
    if not mergeable_parents:
        return prefixes

    seen_parents: set[str] = set()
    out: list[str] = []
    for p in prefixes:
        parent = p[:-1]
        if parent in mergeable_parents:
            if parent not in seen_parents:
                out.append(parent)
                seen_parents.add(parent)
        else:
            out.append(p)
    return out

"""Serializer for the OVH VoIP incoming-blacklist CSV format.

Format (confirmed empirically — no official spec):
  header: callNumber,nature,type
  rows:   +33162,international,incomingBlackList
Separator: comma. Encoding: UTF-8 without BOM. Line ending: LF.
"""

from __future__ import annotations

from pathlib import Path

CSV_HEADER = "callNumber,nature,type"
NATURE = "international"
TYPE_INCOMING_BLACKLIST = "incomingBlackList"


def render_csv(prefixes: list[str]) -> str:
    lines = [CSV_HEADER]
    for prefix in prefixes:
        lines.append(f"{prefix},{NATURE},{TYPE_INCOMING_BLACKLIST}")
    return "\n".join(lines) + "\n"


def write_ovh_csv(prefixes: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_csv(prefixes), encoding="utf-8", newline="\n")

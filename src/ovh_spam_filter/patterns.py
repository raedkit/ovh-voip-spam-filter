from dataclasses import dataclass
from typing import Literal

PatternSource = Literal["api", "cache", "arcep-hardcoded"]


@dataclass(frozen=True)
class BlockPattern:
    """A pattern flagged for blocking.

    `raw` is the Saracroche-style pattern in international form without `+`
    and with `#` as trailing wildcards (e.g. `33162######`).
    `name` is the human label from the source (`Préfixe démarchage ARCEP`, etc.).
    """

    name: str
    raw: str

    def to_ovh_prefix(self) -> str:
        digits = self.raw.rstrip("#")
        return f"+{digits}"

    @property
    def is_arcep(self) -> bool:
        return "ARCEP" in self.name


def prioritize(patterns: list[BlockPattern]) -> list[BlockPattern]:
    """Stable sort that puts ARCEP entries first, preserving input order within each group.

    Used so that `--max-entries N` truncation always keeps the ARCEP coverage critical
    to the user's reported numbers.
    """
    arcep = [p for p in patterns if p.is_arcep]
    other = [p for p in patterns if not p.is_arcep]
    return arcep + other


def deduplicate_ovh_prefixes(prefixes: list[str]) -> list[str]:
    """Drop prefixes that are subsumed by a shorter prefix already present.

    OVH matches by prefix, so `+33162345` is redundant if `+33162` is also in the list.
    Preserves the order of first occurrence.
    """
    kept: list[str] = []
    for p in prefixes:
        if any(p != k and p.startswith(k) for k in kept):
            continue
        kept.append(p)
    return kept

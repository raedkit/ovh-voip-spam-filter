"""Hard-coded ARCEP démarchage prefix ranges.

Source: ARCEP numbering plan decision (effective 2022-09-01).
This is the last-resort fallback when the Saracroche API is unreachable
and no local cache is available.

Each prefix is the international form (33...) and matches any number
starting with that sequence. Saracroche's main list is a superset.
"""

from ovh_spam_filter.patterns import BlockPattern

_METROPOLE_PREFIXES = [
    "162", "163",  # operators (réseaux des démarcheurs niveau 1)
    "270", "271",
    "377", "378",
    "424", "425",
    "568", "569",
    "948", "949",
]

_OUTRE_MER_PREFIXES = ["9475", "9476", "9477", "9478", "9479"]

_ONOFF_PREFIXES = ["64466", "64467", "64468", "64469", "7568", "7569"]


def arcep_fallback_patterns() -> list[BlockPattern]:
    out: list[BlockPattern] = []
    for p in _METROPOLE_PREFIXES:
        out.append(BlockPattern(name="Préfixe démarchage ARCEP (métropole)", raw=f"33{p}"))
    for p in _OUTRE_MER_PREFIXES:
        out.append(BlockPattern(name="Préfixe démarchage ARCEP (outre-mer)", raw=f"33{p}"))
    for p in _ONOFF_PREFIXES:
        out.append(BlockPattern(name="Préfixe démarchage ARCEP (OnOff)", raw=f"33{p}"))
    return out

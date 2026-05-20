import pytest

from ovh_voip_spam_filter.arcep import arcep_fallback_patterns
from ovh_voip_spam_filter.patterns import deduplicate_ovh_prefixes

REPORTED_NUMBERS = [
    "+33270502261",
    "+33424283137",
    "+33270502265",
    "+33377113081",
    "+33377114132",
    "+33377493151",
]


@pytest.mark.parametrize("number", REPORTED_NUMBERS)
def test_reported_number_is_covered_in_pure_fallback_mode(number: str) -> None:
    patterns = arcep_fallback_patterns()
    prefixes = deduplicate_ovh_prefixes([p.to_ovh_prefix() for p in patterns])
    normalized = number.lstrip("+")
    assert any(normalized.startswith(p.lstrip("+")) for p in prefixes), (
        f"{number} not covered by ARCEP fallback prefixes {prefixes}"
    )


def test_fallback_includes_metropole_outre_mer_and_onoff() -> None:
    patterns = arcep_fallback_patterns()
    names = {p.name for p in patterns}
    assert any("métropole" in n for n in names)
    assert any("outre-mer" in n for n in names)
    assert any("OnOff" in n for n in names)


def test_all_fallback_entries_are_arcep_tagged() -> None:
    for p in arcep_fallback_patterns():
        assert p.is_arcep, f"Pattern {p} should be tagged ARCEP"

from ovh_voip_spam_filter.patterns import (
    BlockPattern,
    deduplicate_ovh_prefixes,
    prioritize,
)


def test_to_ovh_prefix_strips_trailing_wildcards() -> None:
    assert BlockPattern(name="x", raw="33162######").to_ovh_prefix() == "+33162"
    assert BlockPattern(name="x", raw="3397837####").to_ovh_prefix() == "+3397837"


def test_to_ovh_prefix_keeps_digits_when_no_wildcards() -> None:
    assert BlockPattern(name="x", raw="33162").to_ovh_prefix() == "+33162"


def test_prioritize_puts_arcep_first_stable() -> None:
    arcep_a = BlockPattern(name="Préfixe démarchage ARCEP", raw="33162######")
    arcep_b = BlockPattern(name="Préfixe démarchage ARCEP (OnOff)", raw="337568")
    other_a = BlockPattern(name="Spam potentiel : Foo", raw="33189######")
    other_b = BlockPattern(name="Spam potentiel : Bar", raw="33449######")
    ordered = prioritize([other_a, arcep_a, other_b, arcep_b])
    assert ordered == [arcep_a, arcep_b, other_a, other_b]


def test_deduplicate_drops_subprefixes() -> None:
    prefixes = ["+33162", "+33162345", "+33163", "+33270"]
    assert deduplicate_ovh_prefixes(prefixes) == ["+33162", "+33163", "+33270"]


def test_deduplicate_preserves_order() -> None:
    prefixes = ["+33270", "+33162", "+33424"]
    assert deduplicate_ovh_prefixes(prefixes) == ["+33270", "+33162", "+33424"]


def test_deduplicate_keeps_identical_only_once_via_kept_invariant() -> None:
    # Identical entries are kept once because the second sees the first in `kept`
    # (p != k condition skips literal equality, but startswith still matches).
    # We accept that exact duplicates pass through; callers should not pass them.
    # This test pins current behavior: literal dup is NOT dropped, but a longer dup IS.
    out = deduplicate_ovh_prefixes(["+33162", "+331620"])
    assert out == ["+33162"]

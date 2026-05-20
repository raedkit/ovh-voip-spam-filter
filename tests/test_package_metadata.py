"""Ensure the package's __version__ is wired to the distribution metadata."""

from __future__ import annotations

from importlib.metadata import version

import ovh_voip_spam_filter


def test_version_is_a_non_empty_string() -> None:
    assert isinstance(ovh_voip_spam_filter.__version__, str)
    assert ovh_voip_spam_filter.__version__
    assert ovh_voip_spam_filter.__version__ != "0.0.0+unknown", (
        "Package metadata lookup failed — was the package installed with `pip install -e .` ?"
    )


def test_version_matches_distribution() -> None:
    assert ovh_voip_spam_filter.__version__ == version("ovh-voip-spam-filter")

"""CLI parser smoke tests: every subcommand accepts --help and reports the canonical prog name."""

from __future__ import annotations

import pytest

from ovh_voip_spam_filter import cli

PROG_NAME = "ovh-voip-spam-filter"


@pytest.mark.parametrize("subcommand", ["generate", "status", "discover", "sync"])
def test_subcommand_help_exits_zero_and_shows_prog_name(
    subcommand: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main([subcommand, "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert PROG_NAME in out, f"--help for `{subcommand}` did not mention {PROG_NAME}"


def test_top_level_help_lists_all_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for sub in ["generate", "status", "discover", "sync"]:
        assert sub in out
    assert PROG_NAME in out


def test_missing_subcommand_is_a_clear_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2  # argparse usage error

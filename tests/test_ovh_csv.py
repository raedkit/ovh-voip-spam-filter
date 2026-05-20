from pathlib import Path

from ovh_spam_filter.ovh_csv import CSV_HEADER, render_csv, write_ovh_csv


def test_render_has_header_and_correct_row_format() -> None:
    out = render_csv(["+33162", "+33270"])
    lines = out.split("\n")
    assert lines[0] == CSV_HEADER
    assert lines[1] == "+33162,international,incomingBlackList"
    assert lines[2] == "+33270,international,incomingBlackList"


def test_render_ends_with_single_trailing_newline() -> None:
    out = render_csv(["+33162"])
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_render_empty_list_still_has_header() -> None:
    out = render_csv([])
    assert out == CSV_HEADER + "\n"


def test_write_uses_utf8_lf_and_no_bom(tmp_path: Path) -> None:
    target = tmp_path / "out.csv"
    write_ovh_csv(["+33162"], target)
    raw = target.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM should not be present"
    assert b"\r\n" not in raw, "must be LF only, no CRLF"
    assert raw.decode("utf-8").splitlines() == [
        CSV_HEADER,
        "+33162,international,incomingBlackList",
    ]


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "out.csv"
    write_ovh_csv(["+33162"], target)
    assert target.exists()

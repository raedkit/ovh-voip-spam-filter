"""logging_setup writes ISO-stamped, level-tagged lines to stderr."""

from __future__ import annotations

import logging
import re
import sys

import pytest

from ovh_voip_spam_filter import logging_setup


@pytest.fixture(autouse=True)
def _reset_root_logger() -> None:
    """logging_setup.setup() is idempotent at root; isolate handlers between tests."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    # Remove only our StreamHandlers that point to stderr (don't disturb pytest's caplog).
    for handler in list(root.handlers):
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stderr:
            root.removeHandler(handler)
    yield
    # Restore exactly the original handler set + level
    for handler in list(root.handlers):
        if handler not in saved_handlers:
            root.removeHandler(handler)
    for handler in saved_handlers:
        if handler not in root.handlers:
            root.addHandler(handler)
    root.setLevel(saved_level)


def _our_handler() -> logging.StreamHandler | None:
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stderr:
            return handler
    return None


def test_setup_attaches_stderr_handler() -> None:
    logging_setup.setup("INFO")
    handler = _our_handler()
    assert handler is not None


def test_setup_is_idempotent() -> None:
    logging_setup.setup("INFO")
    handlers_after_first = [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
    ]
    logging_setup.setup("DEBUG")
    handlers_after_second = [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
    ]
    assert len(handlers_after_first) == 1
    assert len(handlers_after_second) == 1


def test_log_format_iso_zulu_and_level() -> None:
    logging_setup.setup("INFO")
    handler = _our_handler()
    assert handler is not None
    formatter = handler.formatter
    assert formatter is not None
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z \[INFO\] hello world$",
        formatted,
    ), formatted


def test_log_level_is_applied() -> None:
    logging_setup.setup("WARNING")
    assert logging.getLogger().level == logging.WARNING
    logging_setup.setup("DEBUG")  # idempotent, level should NOT change again
    assert logging.getLogger().level == logging.WARNING

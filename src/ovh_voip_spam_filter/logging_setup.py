"""Logging setup for non-interactive (cron/K8s) usage.

Writes plain-text records to stderr with ISO-8601 UTC timestamp and level:

    2026-05-20T09:42:13Z [INFO] message...

Stdout is reserved for tool output that other programs might consume
(e.g. `discover` printing IDs). Diagnostics go to stderr so they can
be captured separately by cron/K8s log shippers.
"""

from __future__ import annotations

import logging
import sys
import time

_HANDLER_TAG = "ovh_voip_spam_filter_stderr_handler"


class _IsoFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created))


def setup(level: str = "INFO") -> None:
    """Attach our stderr handler to the root logger. Idempotent w.r.t. our own handler.

    Coexists with pytest's caplog handler (which also lives on root).
    """
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, "_tag", None) == _HANDLER_TAG:
            return  # already installed
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(_IsoFormatter("%(asctime)s [%(levelname)s] %(message)s"))
    handler._tag = _HANDLER_TAG  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get(name: str) -> logging.Logger:
    return logging.getLogger(name)

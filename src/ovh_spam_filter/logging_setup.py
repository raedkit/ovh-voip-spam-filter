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


class _IsoFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        tz_local = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created))
        return tz_local


def setup(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # idempotent
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(_IsoFormatter("%(asctime)s [%(levelname)s] %(message)s"))
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get(name: str) -> logging.Logger:
    return logging.getLogger(name)

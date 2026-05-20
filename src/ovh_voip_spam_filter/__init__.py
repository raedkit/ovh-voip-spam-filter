"""ovh-voip-spam-filter — reconcile your OVH SIP blacklist with the Saracroche community list."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ovh-voip-spam-filter")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

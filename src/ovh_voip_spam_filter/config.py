"""Credentials and runtime configuration loader.

Precedence (highest first):
  1. CLI flags             (handled in cli.py)
  2. Environment variables (operational mode: Docker / K8s)
  3. JSON config file      (developer convenience, default .ovh-credentials.json)

Env vars:
  OVH_ENDPOINT             ovh-eu | ovh-ca | ovh-us           (default: ovh-eu)
  OVH_APPLICATION_KEY      (required for signed requests)
  OVH_APPLICATION_SECRET   (required for signed requests)
  OVH_CONSUMER_KEY         (required for signed requests)
  OVH_BILLING_ACCOUNT      target billing account              (required for sync)
  OVH_SERVICE_NAME         target SIP line                     (required for sync)
  RATE_LIMIT_MS            min ms between calls               (default: 1000)
  LOG_LEVEL                DEBUG | INFO | WARNING | ERROR     (default: INFO)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from ovh_voip_spam_filter.ovh_api import ENDPOINTS, OvhCredentials

DEFAULT_CONFIG_PATH = Path(".ovh-credentials.json")
DEFAULT_RATE_LIMIT_MS = 1000


@dataclass(frozen=True)
class AppConfig:
    credentials: OvhCredentials
    billing_account: str | None
    service_name: str | None
    rate_limit_ms: int
    log_level: str


class ConfigError(RuntimeError):
    pass


def load(config_path: Path | None = None) -> AppConfig:
    file_data = _load_file(config_path or DEFAULT_CONFIG_PATH)

    endpoint = os.getenv("OVH_ENDPOINT") or file_data.get("endpoint") or "ovh-eu"
    if endpoint not in ENDPOINTS:
        raise ConfigError(
            f"Unknown OVH_ENDPOINT {endpoint!r} (expected one of {sorted(ENDPOINTS)})"
        )

    application_key = os.getenv("OVH_APPLICATION_KEY") or file_data.get("application_key")
    application_secret = os.getenv("OVH_APPLICATION_SECRET") or file_data.get("application_secret")
    consumer_key = os.getenv("OVH_CONSUMER_KEY") or file_data.get("consumer_key")

    rate_limit_ms = (
        _int_env("RATE_LIMIT_MS") or file_data.get("rate_limit_ms") or DEFAULT_RATE_LIMIT_MS
    )

    return AppConfig(
        credentials=OvhCredentials(
            endpoint=endpoint,
            application_key=application_key or "",
            application_secret=application_secret or "",
            consumer_key=consumer_key,
        ),
        billing_account=os.getenv("OVH_BILLING_ACCOUNT") or file_data.get("billing_account"),
        service_name=os.getenv("OVH_SERVICE_NAME") or file_data.get("service_name"),
        rate_limit_ms=int(rate_limit_ms),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


def require_signed_credentials(config: AppConfig) -> OvhCredentials:
    """Validate that we have everything needed for signed OVH API calls.

    Raises ConfigError with a clear remediation message if any is missing.
    """
    creds = config.credentials
    missing = []
    if not creds.application_key:
        missing.append("OVH_APPLICATION_KEY")
    if not creds.application_secret:
        missing.append("OVH_APPLICATION_SECRET")
    if not creds.consumer_key:
        missing.append("OVH_CONSUMER_KEY")
    if missing:
        raise ConfigError(
            f"Missing required OVH credentials: {', '.join(missing)}. "
            f"Generate them at https://api.ovh.com/createToken/ (see README → 'OVH API setup')."
        )
    return creds


def require_target(config: AppConfig) -> tuple[str, str]:
    """Validate billing_account + service_name presence (required for sync)."""
    if not config.billing_account or not config.service_name:
        raise ConfigError(
            "Missing OVH_BILLING_ACCOUNT and/or OVH_SERVICE_NAME. "
            "Run `discover` to list them, then set them in env or config."
        )
    return config.billing_account, config.service_name


def _int_env(key: str) -> int | None:
    val = os.getenv(key)
    if val is None or val == "":
        return None
    try:
        return int(val)
    except ValueError as exc:
        raise ConfigError(f"Env {key}={val!r} is not an integer") from exc


def _load_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must be a JSON object")
    return data

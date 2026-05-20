"""Minimal OVH API client (stdlib only).

Implements OVH's "$1$" signed-request scheme:

    signature = "$1$" + sha1(
        application_secret + "+" + consumer_key + "+" +
        METHOD + "+" + URL + "+" + BODY + "+" + TIMESTAMP
    ).hexdigest()

Designed for a non-interactive cron/K8s context:
  - Client-side throttle between calls (default 1 req/s, configurable).
  - 429 backoff respecting Retry-After header, with jittered exponential
    fallback and an absolute cap.
  - Auto-adapts the throttle: after 3 consecutive 429s the inter-call
    interval is doubled for the rest of the session (no manual tuning
    required if OVH's per-account quota differs from the documented 60/min).
"""

from __future__ import annotations

import hashlib
import json
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ovh_voip_spam_filter import __version__
from ovh_voip_spam_filter.logging_setup import get as _get_logger

logger = _get_logger(__name__)

USER_AGENT = (
    f"ovh-voip-spam-filter/{__version__} (+https://github.com/raedkit/ovh-voip-spam-filter)"
)

ENDPOINTS = {
    "ovh-eu": "https://eu.api.ovh.com/1.0",
    "ovh-ca": "https://ca.api.ovh.com/1.0",
    "ovh-us": "https://api.us.ovhcloud.com/1.0",
}

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES_ON_429 = 6
BACKOFF_CAP_SECONDS = 30.0
AUTO_ADAPT_429_THRESHOLD = 3  # consecutive 429s before doubling the throttle


class OvhApiError(RuntimeError):
    def __init__(self, status: int, message: str, body: str = ""):
        super().__init__(f"OVH API {status}: {message}")
        self.status = status
        self.body = body


@dataclass(frozen=True)
class OvhCredentials:
    endpoint: str  # "ovh-eu" etc.
    application_key: str
    application_secret: str
    consumer_key: str | None  # None if running an unsigned probe

    def base_url(self) -> str:
        try:
            return ENDPOINTS[self.endpoint]
        except KeyError as exc:
            raise ValueError(f"Unknown endpoint {self.endpoint!r}") from exc


class OvhClient:
    def __init__(
        self,
        credentials: OvhCredentials,
        min_interval_seconds: float = 0.0,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries_on_429: int = DEFAULT_MAX_RETRIES_ON_429,
        _sleep: Callable[[float], None] = time.sleep,
        _monotonic: Callable[[], float] = time.monotonic,
        _rand: Callable[[], float] = random.random,
    ) -> None:
        self.credentials = credentials
        self.min_interval_seconds = float(min_interval_seconds)
        self.timeout = timeout
        self.max_retries_on_429 = max_retries_on_429
        self._sleep = _sleep
        self._monotonic = _monotonic
        self._rand = _rand
        self._last_call_at: float = 0.0
        self._consecutive_429: int = 0
        self._throttle_adaptations: int = 0

    @property
    def total_throttle_adaptations(self) -> int:
        """Number of times min_interval_seconds was auto-doubled this session."""
        return self._throttle_adaptations

    # ---------- low-level signed request ----------

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        signed: bool = True,
    ) -> Any:
        url = self.credentials.base_url() + path
        body_str = json.dumps(body) if body is not None else ""

        if signed and self.min_interval_seconds > 0:
            gap = self._monotonic() - self._last_call_at
            sleep_for = self.min_interval_seconds - gap
            if sleep_for > 0:
                self._sleep(sleep_for)

        attempt = 0
        backoff = 1.0
        while True:
            headers = self._headers(method, url, body_str, signed=signed)
            req = urllib.request.Request(
                url=url,
                data=body_str.encode("utf-8") if body_str else None,
                headers=headers,
                method=method,
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    self._last_call_at = self._monotonic()
                    self._consecutive_429 = 0
                    raw = resp.read()
                    if not raw:
                        return None
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                self._last_call_at = self._monotonic()
                raw = (exc.read() or b"").decode("utf-8", errors="replace")
                if exc.code == 429 and attempt < self.max_retries_on_429:
                    attempt += 1
                    self._consecutive_429 += 1
                    sleep_for = self._compute_429_sleep(exc.headers.get("Retry-After"), backoff)
                    backoff = min(backoff * 2, BACKOFF_CAP_SECONDS)
                    self._maybe_adapt_throttle()
                    logger.warning(
                        "429 on %s %s, sleeping %.1fs (attempt %d/%d, consecutive=%d)",
                        method,
                        path,
                        sleep_for,
                        attempt,
                        self.max_retries_on_429,
                        self._consecutive_429,
                    )
                    self._sleep(sleep_for)
                    continue
                message = self._extract_message(raw) or exc.reason
                raise OvhApiError(exc.code, message, raw) from exc
            except urllib.error.URLError as exc:
                raise OvhApiError(0, f"network error: {exc}", "") from exc

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("POST", path, body=body)

    def put(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("PUT", path, body=body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    # ---------- backoff helpers ----------

    def _compute_429_sleep(self, retry_after_header: str | None, backoff: float) -> float:
        if retry_after_header:
            try:
                return max(float(retry_after_header), 0.5)
            except ValueError:
                pass  # falls through to jittered exponential
        jitter = 1.0 + (self._rand() * 0.4 - 0.2)  # ±20%
        return float(min(backoff * jitter, BACKOFF_CAP_SECONDS))

    def _maybe_adapt_throttle(self) -> None:
        if self._consecutive_429 >= AUTO_ADAPT_429_THRESHOLD and self.min_interval_seconds > 0:
            old = self.min_interval_seconds
            self.min_interval_seconds = min(old * 2.0, 10.0)
            self._consecutive_429 = 0
            self._throttle_adaptations += 1
            logger.warning(
                "Auto-adapting throttle after %d consecutive 429s: %.2fs -> %.2fs",
                AUTO_ADAPT_429_THRESHOLD,
                old,
                self.min_interval_seconds,
            )

    # ---------- signature ----------

    def _headers(self, method: str, url: str, body_str: str, signed: bool) -> dict[str, str]:
        headers = {
            "X-Ovh-Application": self.credentials.application_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if not signed:
            return headers
        if self.credentials.consumer_key is None:
            raise ValueError("Consumer key is required for signed requests")
        timestamp = str(int(time.time()))
        to_sign = "+".join(
            [
                self.credentials.application_secret,
                self.credentials.consumer_key,
                method,
                url,
                body_str,
                timestamp,
            ]
        )
        signature = "$1$" + hashlib.sha1(to_sign.encode("utf-8")).hexdigest()
        headers["X-Ovh-Consumer"] = self.credentials.consumer_key
        headers["X-Ovh-Timestamp"] = timestamp
        headers["X-Ovh-Signature"] = signature
        return headers

    @staticmethod
    def _extract_message(raw: str) -> str | None:
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
        if isinstance(payload, dict):
            return payload.get("message") or payload.get("error")
        return None

    # ---------- high-level telephony helpers ----------

    def whoami(self) -> dict[str, Any]:
        return self.get("/me") or {}

    def list_billing_accounts(self) -> list[str]:
        return self.get("/telephony") or []

    def list_screen_services(self, billing_account: str) -> list[str]:
        return self.get(f"/telephony/{billing_account}/screen") or []

    def get_screen_state(self, billing_account: str, service_name: str) -> dict[str, Any]:
        return self.get(f"/telephony/{billing_account}/screen/{service_name}") or {}

    def set_screen_state(
        self,
        billing_account: str,
        service_name: str,
        *,
        incoming: str | None = None,
        outgoing: str | None = None,
    ) -> None:
        body: dict[str, Any] = {}
        if incoming is not None:
            body["incomingScreenList"] = incoming
        if outgoing is not None:
            body["outgoingScreenList"] = outgoing
        if not body:
            return
        self.put(f"/telephony/{billing_account}/screen/{service_name}", body)

    def list_screen_list_ids(self, billing_account: str, service_name: str) -> list[int]:
        return self.get(f"/telephony/{billing_account}/screen/{service_name}/screenLists") or []

    def get_screen_list_entry(
        self, billing_account: str, service_name: str, entry_id: int
    ) -> dict[str, Any]:
        return (
            self.get(f"/telephony/{billing_account}/screen/{service_name}/screenLists/{entry_id}")
            or {}
        )

    def add_screen_list_entry(
        self,
        billing_account: str,
        service_name: str,
        *,
        call_number: str,
        nature: str = "international",
        type_: str = "incomingBlackList",
    ) -> None:
        self.post(
            f"/telephony/{billing_account}/screen/{service_name}/screenLists",
            body={"callNumber": call_number, "nature": nature, "type": type_},
        )

    def delete_screen_list_entry(
        self, billing_account: str, service_name: str, entry_id: int
    ) -> None:
        self.delete(f"/telephony/{billing_account}/screen/{service_name}/screenLists/{entry_id}")

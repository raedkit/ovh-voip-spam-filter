"""Tests for the OVH signed client. urlopen is stubbed."""

from __future__ import annotations

import hashlib
import io
import json
from email.message import Message
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from ovh_voip_spam_filter import ovh_api
from ovh_voip_spam_filter.ovh_api import OvhApiError, OvhClient, OvhCredentials


def _creds(consumer_key: str | None = "ck-test") -> OvhCredentials:
    return OvhCredentials(
        endpoint="ovh-eu",
        application_key="ak-test",
        application_secret="as-test",
        consumer_key=consumer_key,
    )


class _FakeResponse:
    def __init__(self, body: bytes = b"", headers: dict[str, str] | None = None):
        self._body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _http_error(status: int, headers: dict[str, str] | None = None, body: bytes = b"") -> HTTPError:
    msg = Message()
    for k, v in (headers or {}).items():
        msg[k] = v
    return HTTPError(
        url="https://eu.api.ovh.com/1.0/anything",
        code=status,
        msg=f"status {status}",
        hdrs=msg,
        fp=io.BytesIO(body),
    )


# ---------- signature ----------


def test_signature_format_matches_ovh_spec() -> None:
    client = OvhClient(_creds())
    method, url, body, timestamp = "GET", "https://example/path", "", "1700000000"

    with patch.object(ovh_api.time, "time", return_value=int(timestamp)):
        headers = client._headers(method, url, body, signed=True)

    expected_signed = "+".join(["as-test", "ck-test", method, url, body, timestamp])
    expected_sig = "$1$" + hashlib.sha1(expected_signed.encode("utf-8")).hexdigest()
    assert headers["X-Ovh-Application"] == "ak-test"
    assert headers["X-Ovh-Consumer"] == "ck-test"
    assert headers["X-Ovh-Timestamp"] == timestamp
    assert headers["X-Ovh-Signature"] == expected_sig


def test_unsigned_request_has_no_consumer_or_signature() -> None:
    client = OvhClient(_creds(consumer_key=None))
    headers = client._headers("GET", "https://example/path", "", signed=False)
    assert "X-Ovh-Consumer" not in headers
    assert "X-Ovh-Signature" not in headers
    assert headers["X-Ovh-Application"] == "ak-test"


def test_signed_request_without_consumer_key_raises() -> None:
    client = OvhClient(_creds(consumer_key=None))
    with pytest.raises(ValueError, match="Consumer key"):
        client._headers("GET", "https://example/path", "", signed=True)


# ---------- happy path ----------


def test_get_returns_parsed_json() -> None:
    client = OvhClient(_creds())
    payload = {"nichandle": "abc-ovh", "email": "x@example.com"}
    with patch("urllib.request.urlopen", return_value=_FakeResponse(json.dumps(payload).encode())):
        result = client.get("/me")
    assert result == payload


def test_empty_response_returns_none() -> None:
    client = OvhClient(_creds())
    with patch("urllib.request.urlopen", return_value=_FakeResponse(b"")):
        assert client.delete("/anything") is None


# ---------- throttle ----------


def test_throttle_sleeps_to_respect_min_interval() -> None:
    sleeps: list[float] = []
    # Each request triggers _monotonic twice: once for gap calc, once for last_call_at.
    # First request: gap_calc(1000.0) -> last_call_at=1000.05
    # Second request: gap_calc(1000.05) -> last_call_at=1001.10
    times = iter([1000.0, 1000.05, 1000.05, 1001.10])
    client = OvhClient(
        _creds(),
        min_interval_seconds=1.0,
        _sleep=sleeps.append,
        _monotonic=lambda: next(times),
    )
    with patch("urllib.request.urlopen", return_value=_FakeResponse(b"{}")):
        client.get("/anything")
        client.get("/anything")  # gap=0 ⇒ should sleep 1.0s
    assert sleeps == [pytest.approx(1.0, abs=0.01)]


# ---------- 429 backoff ----------


def test_429_with_retry_after_respects_header_and_retries() -> None:
    sleeps: list[float] = []
    rands = iter([0.5, 0.5])
    client = OvhClient(
        _creds(),
        min_interval_seconds=0,
        _sleep=sleeps.append,
        _rand=lambda: next(rands),
    )
    payload = {"id": 42}
    responses = [
        _http_error(429, headers={"Retry-After": "3"}),
        _FakeResponse(json.dumps(payload).encode()),
    ]

    def fake_urlopen(*args, **kwargs):
        r = responses.pop(0)
        if isinstance(r, HTTPError):
            raise r
        return r

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = client.get("/anything")
    assert result == payload
    assert sleeps == [pytest.approx(3.0)]


def test_429_without_retry_after_uses_jittered_exponential() -> None:
    sleeps: list[float] = []
    # rand=0.5 -> jitter = 1.0 + (0.5*0.4 - 0.2) = 1.0 → backoff * 1.0
    client = OvhClient(
        _creds(),
        min_interval_seconds=0,
        _sleep=sleeps.append,
        _rand=lambda: 0.5,
    )
    payload = {"id": 1}
    responses = [
        _http_error(429),
        _http_error(429),
        _FakeResponse(json.dumps(payload).encode()),
    ]

    def fake_urlopen(*args, **kwargs):
        r = responses.pop(0)
        if isinstance(r, HTTPError):
            raise r
        return r

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        client.get("/anything")
    # First retry: backoff=1.0, jitter=1.0 → 1.0s. Second: backoff=2.0, jitter=1.0 → 2.0s.
    assert sleeps == [pytest.approx(1.0), pytest.approx(2.0)]


def test_three_consecutive_429s_doubles_throttle() -> None:
    sleeps: list[float] = []
    client = OvhClient(
        _creds(),
        min_interval_seconds=1.0,
        _sleep=sleeps.append,
        _rand=lambda: 0.5,
    )
    payload = {"id": 1}
    # 3 consecutive 429s → throttle should double from 1.0 to 2.0
    responses = [
        _http_error(429),
        _http_error(429),
        _http_error(429),
        _FakeResponse(json.dumps(payload).encode()),
    ]

    def fake_urlopen(*args, **kwargs):
        r = responses.pop(0)
        if isinstance(r, HTTPError):
            raise r
        return r

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        client.get("/anything")
    assert client.min_interval_seconds == pytest.approx(2.0)
    assert client.total_throttle_adaptations == 1


def test_429_exhausts_retries_then_raises() -> None:
    client = OvhClient(
        _creds(),
        min_interval_seconds=0,
        max_retries_on_429=2,
        _sleep=lambda _: None,
        _rand=lambda: 0.5,
    )
    err = _http_error(429)
    with patch("urllib.request.urlopen", side_effect=err), pytest.raises(OvhApiError) as ei:
        client.get("/anything")
    assert ei.value.status == 429


def test_non_429_error_propagates_immediately() -> None:
    client = OvhClient(_creds(), _sleep=lambda _: None)
    err = _http_error(403, body=b'{"message":"forbidden"}')
    with patch("urllib.request.urlopen", side_effect=err), pytest.raises(OvhApiError) as ei:
        client.get("/anything")
    assert ei.value.status == 403
    assert "forbidden" in str(ei.value)


# ---------- high-level helpers ----------


def test_add_screen_list_entry_posts_correct_body() -> None:
    client = OvhClient(_creds(), _sleep=lambda _: None)
    captured: dict[str, Any] = {}

    def fake_urlopen(req, *args, **kwargs):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = req.data.decode("utf-8") if req.data else ""
        return _FakeResponse(b"")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        client.add_screen_list_entry(
            "ab-12345-ovh",
            "0033xxxxxxxx",
            call_number="+33162",
        )

    assert captured["method"] == "POST"
    assert "/telephony/ab-12345-ovh/screen/0033xxxxxxxx/screenLists" in captured["url"]
    body = json.loads(captured["body"])
    assert body == {
        "callNumber": "+33162",
        "nature": "international",
        "type": "incomingBlackList",
    }

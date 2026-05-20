import json
from pathlib import Path

import pytest

from ovh_spam_filter import config


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for k in [
        "OVH_ENDPOINT",
        "OVH_APPLICATION_KEY",
        "OVH_APPLICATION_SECRET",
        "OVH_CONSUMER_KEY",
        "OVH_BILLING_ACCOUNT",
        "OVH_SERVICE_NAME",
        "RATE_LIMIT_MS",
        "LOG_LEVEL",
    ]:
        monkeypatch.delenv(k, raising=False)


def test_env_takes_precedence_over_file(monkeypatch, tmp_path: Path) -> None:
    cfg_file = tmp_path / "creds.json"
    cfg_file.write_text(
        json.dumps({"application_key": "from-file", "application_secret": "fs", "consumer_key": "fc"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OVH_APPLICATION_KEY", "from-env")
    monkeypatch.setenv("OVH_APPLICATION_SECRET", "es")
    monkeypatch.setenv("OVH_CONSUMER_KEY", "ec")

    cfg = config.load(cfg_file)
    assert cfg.credentials.application_key == "from-env"
    assert cfg.credentials.application_secret == "es"
    assert cfg.credentials.consumer_key == "ec"


def test_default_endpoint_is_ovh_eu(monkeypatch, tmp_path: Path) -> None:
    cfg = config.load(tmp_path / "absent.json")
    assert cfg.credentials.endpoint == "ovh-eu"


def test_invalid_endpoint_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OVH_ENDPOINT", "ovh-mars")
    with pytest.raises(config.ConfigError, match="Unknown OVH_ENDPOINT"):
        config.load(tmp_path / "absent.json")


def test_default_rate_limit_is_1000ms(monkeypatch, tmp_path: Path) -> None:
    cfg = config.load(tmp_path / "absent.json")
    assert cfg.rate_limit_ms == 1000


def test_rate_limit_from_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RATE_LIMIT_MS", "500")
    cfg = config.load(tmp_path / "absent.json")
    assert cfg.rate_limit_ms == 500


def test_rate_limit_non_integer_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RATE_LIMIT_MS", "not-a-number")
    with pytest.raises(config.ConfigError, match="not an integer"):
        config.load(tmp_path / "absent.json")


def test_require_signed_credentials_complains_clearly(monkeypatch, tmp_path: Path) -> None:
    cfg = config.load(tmp_path / "absent.json")
    with pytest.raises(config.ConfigError) as ei:
        config.require_signed_credentials(cfg)
    msg = str(ei.value)
    assert "OVH_APPLICATION_KEY" in msg
    assert "OVH_APPLICATION_SECRET" in msg
    assert "OVH_CONSUMER_KEY" in msg
    assert "createToken" in msg


def test_require_target_complains_clearly(monkeypatch, tmp_path: Path) -> None:
    cfg = config.load(tmp_path / "absent.json")
    with pytest.raises(config.ConfigError) as ei:
        config.require_target(cfg)
    assert "OVH_BILLING_ACCOUNT" in str(ei.value)
    assert "discover" in str(ei.value)


def test_malformed_json_raises(monkeypatch, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="not valid JSON"):
        config.load(bad)

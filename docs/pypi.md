# PyPI install

The package is published as [`ovh-voip-spam-filter`](https://pypi.org/project/ovh-voip-spam-filter/) on PyPI.

## Install

```bash
pip install ovh-voip-spam-filter
```

This installs the `ovh-voip-spam-filter` console script.

In a virtual environment (recommended):

```bash
python3 -m venv .venv
.venv/bin/pip install ovh-voip-spam-filter
.venv/bin/ovh-voip-spam-filter --help
```

## Run

Configure via environment variables (see [Configuration](configuration.md)):

```bash
export OVH_APPLICATION_KEY=...
export OVH_APPLICATION_SECRET=...
export OVH_CONSUMER_KEY=...
export OVH_BILLING_ACCOUNT=ab-12345-ovh
export OVH_SERVICE_NAME=0033xxxxxxxx

ovh-voip-spam-filter sync
```

Or use a `.ovh-credentials.json` file (see [Configuration](configuration.md#local-development-convenience-ovh-credentialsjson)).

## Use as a library

The package is also importable. For example, to expose the reconcile pipeline programmatically:

```python
from ovh_voip_spam_filter import config, ovh_api, reconcile

cfg = config.load()
creds = config.require_signed_credentials(cfg)
billing_account, service_name = config.require_target(cfg)

client = ovh_api.OvhClient(
    credentials=creds,
    min_interval_seconds=cfg.rate_limit_ms / 1000.0,
)
target = reconcile.load_target()
target_prefixes = reconcile.target_to_prefixes(target)
current = reconcile.load_current(client, billing_account, service_name)
plan = reconcile.compute_plan(target.mode, target_prefixes, current)
result = reconcile.apply_plan(client, billing_account, service_name, plan)
print(result)
```

See [API reference](api-reference.md) for the full module surface.

## Supported Python versions

`>=3.12`. The package is published as a pure Python wheel (`py3-none-any`) so it works on any platform.

## Versioning

Semantic versioning. The package version matches the GitHub release tag (without the `v` prefix).

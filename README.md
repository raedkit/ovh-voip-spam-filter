<div align="center">

# ovh-voip-spam-filter

🇬🇧 **English** · [🇫🇷 Français](README.fr.md)

**Reconcile your OVH SIP incoming blacklist with [Saracroche](https://saracroche.org), the community-driven blocklist of ~16 million French telemarketing numbers.**

[![CI](https://github.com/raedkit/ovh-voip-spam-filter/actions/workflows/ci.yml/badge.svg)](https://github.com/raedkit/ovh-voip-spam-filter/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/raedkit/ovh-voip-spam-filter?display_name=tag&sort=semver)](https://github.com/raedkit/ovh-voip-spam-filter/releases)
[![GHCR](https://img.shields.io/badge/ghcr.io-ovh--voip--spam--filter-blue?logo=docker)](https://github.com/raedkit/ovh-voip-spam-filter/pkgs/container/ovh-voip-spam-filter)
[![PyPI](https://img.shields.io/pypi/v/ovh-voip-spam-filter)](https://pypi.org/project/ovh-voip-spam-filter/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-green)](LICENSE)

📖 **Full documentation: [raedkit.github.io/ovh-voip-spam-filter](https://raedkit.github.io/ovh-voip-spam-filter/)**

</div>

---

> [!WARNING]
> **Use the API (`sync`), not the CSV.**
> The OVH Manager's CSV import **fails past ~80 entries** (empirically confirmed). This project exists to push the same data through the OVH API one prefix at a time, throttled and idempotent. The CSV mode is kept for completeness but is **not** the recommended path.

## Quickstart

```bash
docker run --rm \
  -e OVH_APPLICATION_KEY=... \
  -e OVH_APPLICATION_SECRET=... \
  -e OVH_CONSUMER_KEY=... \
  -e OVH_BILLING_ACCOUNT=... \
  -e OVH_SERVICE_NAME=... \
  ghcr.io/raedkit/ovh-voip-spam-filter:latest sync
```

Or via PyPI:

```bash
pip install ovh-voip-spam-filter
ovh-voip-spam-filter sync
```

Generate an OVH token with [this pre-filled URL](https://api.ovh.com/createToken/?GET=/me&GET=/telephony&GET=/telephony/*&GET=/telephony/*/screen&GET=/telephony/*/screen/*&GET=/telephony/*/screen/*/screenLists&GET=/telephony/*/screen/*/screenLists/*&PUT=/telephony/*/screen/*&POST=/telephony/*/screen/*/screenLists&DELETE=/telephony/*/screen/*/screenLists/*) (minimum scopes pre-checked).

Full setup walkthrough: **[docs/quickstart](https://raedkit.github.io/ovh-voip-spam-filter/quickstart/)**.

## Why this exists

OVH's Manager UI offers a CSV import for the incoming blacklist, but it POSTs each row internally without rate-limiting. The Saracroche list is **643 prefixes** — the import returns HTTP 429 after ~80. This tool does the same job correctly: signed API requests, client-side throttle, exponential backoff on 429, auto-adaptation if OVH tightens the quota. One bootstrap run takes ~13 minutes; subsequent runs are idempotent and take seconds.

## How it works

```
            ┌────────────────────────────┐
            │  Saracroche live API       │
            │  (~643 block-only prefixes)│
            └─────────────┬──────────────┘
                          │  fallback when down
                          ▼
            ┌────────────────────────────┐
            │  Hard-coded ARCEP fallback │
            │  (23 prefixes, additive)   │
            └─────────────┬──────────────┘
                          ▼
            ┌────────────────────────────┐
            │  Diff vs current OVH state │
            │  (GET-first reconciliation)│
            └─────────────┬──────────────┘
                          ▼
            ┌────────────────────────────┐
            │  Signed OVH API push       │
            │  (throttled, 429-aware)    │
            └────────────────────────────┘
```

- **Normal mode** (Saracroche reachable) — strict sync: adds missing prefixes, removes the ones Saracroche removed.
- **Degraded mode** (Saracroche unreachable) — uses the hard-coded ARCEP fallback, **additive only**, never deletes. Anti-regression guarantee.

Details: **[reconciliation semantics](https://raedkit.github.io/ovh-voip-spam-filter/reconciliation/)**.

## Acknowledgments

🙏 **This project would not exist without [Saracroche](https://saracroche.org) by [Camille Bouvat](https://github.com/cbouvat).**

Saracroche is an open-source community blocklist of ~16 million French telemarketing and spam numbers, maintained solo and pro bono since 2020. We consume the [`french-list-arcep-operators`](https://saracroche.org/api/v1/lists/french-list-arcep-operators) endpoint as our primary source of truth, with no caching on the redistribution side — the freshness you get is whatever Saracroche has right now.

If this tool saved you from a spam call, **please support Camille**:

- 💛 [Liberapay](https://liberapay.com/cbouvat) (preferred)
- 💳 [Stripe / one-shot](https://saracroche.org)
- 🐙 [GitHub Sponsors](https://github.com/cbouvat)

Saracroche source:

- 📱 Apps: [iOS](https://apps.apple.com/fr/app/saracroche/id6743679292) · [Android](https://play.google.com/store/apps/details?id=com.cbouvat.android.saracroche)
- 🦊 Code: [Codeberg (android)](https://codeberg.org/cbouvat/saracroche-android) · [GitHub (legacy)](https://github.com/cbouvat)

## Documentation

Full docs at **[raedkit.github.io/ovh-voip-spam-filter](https://raedkit.github.io/ovh-voip-spam-filter/)**:

- [Quickstart](https://raedkit.github.io/ovh-voip-spam-filter/quickstart/) — token generation, discover, sync
- [Configuration](https://raedkit.github.io/ovh-voip-spam-filter/configuration/) — env vars, CLI flags, Kubernetes
- [Docker](https://raedkit.github.io/ovh-voip-spam-filter/docker/) — image details, multi-arch, CronJob sketch
- [PyPI](https://raedkit.github.io/ovh-voip-spam-filter/pypi/) — install + library usage
- [Reconciliation](https://raedkit.github.io/ovh-voip-spam-filter/reconciliation/) — normal vs degraded mode
- [API reference](https://raedkit.github.io/ovh-voip-spam-filter/api-reference/)
- [Roadmap](https://raedkit.github.io/ovh-voip-spam-filter/roadmap/)

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and the PR checklist. By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

Security issues: see [SECURITY.md](SECURITY.md). Please don't open public issues for credential-handling bugs.

## License

[GPL-3.0-or-later](LICENSE) — matches Saracroche.

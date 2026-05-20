# ovh-voip-spam-filter

Reconcile your **OVH SIP incoming blacklist** with [**Saracroche**](https://saracroche.org), the community-driven blocklist of ~16 million French telemarketing numbers.

!!! warning "Use the API, not the CSV"
    The OVH Manager's CSV import **fails past ~80 entries** (empirically confirmed). This project exists to push the same data via the OVH API, throttled to a safe rate, with idempotent reconciliation and 429-aware backoff. The CSV mode is kept for convenience but is **not** the recommended path.

## What it does

- Pulls the [Saracroche live blocklist](https://saracroche.org/api/v1/lists/french-list-arcep-operators) (~643 block-only prefixes covering 16M+ numbers).
- Pushes the diff to your OVH SIP line's incoming blacklist via the signed OVH API, one prefix at a time, throttled to 1 req/s by default.
- Strict reconciliation in normal mode: adds what's missing **and** removes what Saracroche removed.
- Anti-regression: in degraded mode (Saracroche unreachable), falls back to a hard-coded list of 23 ARCEP prefixes and runs **additive only** — never deletes.
- Auto-promotes `incomingScreenList=disabled` to `blacklist` with a WARN log.

## Distribution

Available as:

- **Docker image**: `ghcr.io/raedkit/ovh-voip-spam-filter:latest` (multi-arch amd64 + arm64, ~216 MB)
- **PyPI package**: `pip install ovh-voip-spam-filter`

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

See [Quickstart](quickstart.md) for the full setup walkthrough including OVH token generation.

## Acknowledgments

This project would not exist without [**Saracroche**](https://saracroche.org), an open-source community blocklist created and maintained by [**Camille Bouvat**](https://github.com/cbouvat) — solo, on personal time, fully open-source under GPL-3.0, no ads, no paywalls. The list contains ~16 million phone numbers used by French commercial telemarketers and spam operators, kept up-to-date daily.

We consume Saracroche's `french-list-arcep-operators` endpoint as our primary source of truth. **If this tool saved you from a spam call, please [donate to Camille](https://liberapay.com/cbouvat) or via [Stripe on saracroche.org](https://saracroche.org)**.

- Saracroche apps and source: [Codeberg](https://codeberg.org/cbouvat/saracroche-android) · [GitHub](https://github.com/cbouvat)

## License

GPL-3.0-or-later, matching Saracroche.

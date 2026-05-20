# Quickstart

This walkthrough takes you from zero to a working `sync` against your OVH SIP line in ~10 minutes (plus an ~13 min bootstrap run for the first sync).

## Prerequisites

- A working OVH VoIP/SIP line you can log into in the [OVH Manager](https://www.ovh.com/manager/).
- **Docker** (recommended) or **Python 3.12+** + `pip`.

## 1. Generate an OVH API token

Open [this pre-filled `createToken` URL](https://api.ovh.com/createToken/?GET=/me&GET=/telephony&GET=/telephony/*&GET=/telephony/*/screen&GET=/telephony/*/screen/*&GET=/telephony/*/screen/*/screenLists&GET=/telephony/*/screen/*/screenLists/*&PUT=/telephony/*/screen/*&POST=/telephony/*/screen/*/screenLists&DELETE=/telephony/*/screen/*/screenLists/*) — it requests the minimum required scopes.

1. Log in with your OVH credentials.
2. Choose a validity period (**Unlimited** for permanent personal use, or **1 year** with manual rotation).
3. Click **Create keys**.
4. You'll get three values: `Application Key`, `Application Secret`, `Consumer Key`. Keep them safe.

!!! danger "Never commit these values"
    Treat the three tokens like passwords. If they ever leak (in a chat, screenshot, or commit), [revoke them immediately](https://eu.api.ovh.com/me/api/credential).

## 2. Discover your billing account and SIP line

=== "Docker"

    ```bash
    docker run --rm \
      -e OVH_APPLICATION_KEY=... \
      -e OVH_APPLICATION_SECRET=... \
      -e OVH_CONSUMER_KEY=... \
      ghcr.io/raedkit/ovh-voip-spam-filter:latest discover
    ```

=== "PyPI"

    ```bash
    pip install ovh-voip-spam-filter
    export OVH_APPLICATION_KEY=...
    export OVH_APPLICATION_SECRET=...
    export OVH_CONSUMER_KEY=...
    ovh-voip-spam-filter discover
    ```

Output looks like:

```text
Found 1 billing account(s):

  billing_account = ab-12345-ovh
    service_name    = 0033xxxxxxxx
```

Note the `billing_account` and `service_name` you want to protect.

## 3. Dry-run

Preview what the sync would do without making any changes:

```bash
docker run --rm \
  -e OVH_APPLICATION_KEY=... \
  -e OVH_APPLICATION_SECRET=... \
  -e OVH_CONSUMER_KEY=... \
  -e OVH_BILLING_ACCOUNT=ab-12345-ovh \
  -e OVH_SERVICE_NAME=0033xxxxxxxx \
  ghcr.io/raedkit/ovh-voip-spam-filter:latest sync --dry-run
```

You'll see a reconcile plan and estimated duration.

## 4. Actual sync

Drop `--dry-run`:

```bash
docker run --rm \
  -e OVH_APPLICATION_KEY=... \
  -e OVH_APPLICATION_SECRET=... \
  -e OVH_CONSUMER_KEY=... \
  -e OVH_BILLING_ACCOUNT=ab-12345-ovh \
  -e OVH_SERVICE_NAME=0033xxxxxxxx \
  ghcr.io/raedkit/ovh-voip-spam-filter:latest sync
```

The bootstrap takes about **13 minutes** at the default 1 req/s for 643 entries. Subsequent runs only POST the changes (typically a few seconds).

You'll see progress like:

```text
2026-05-20T12:30:01Z [INFO] Saracroche live: version=2026-05-20T01:00:53+00:00, 1599 patterns total, 643 block-only
2026-05-20T12:30:02Z [INFO] OVH has 0 existing screenList entries; fetching details
2026-05-20T12:30:03Z [INFO] Added +33162 (1/643)
2026-05-20T12:30:04Z [INFO] Added +33163 (2/643)
...
2026-05-20T12:43:14Z [INFO] Sync complete: added=643 removed=0 failed=0 duration=792.5s throttle_adapts=0
```

## 5. Verify

Either re-run `sync` (should be idempotent: 0 changes), or log into the OVH Manager and check the Filtrage des appels section of your SIP line — the blacklist now contains the prefixes.

If you want to test functionally, ask someone to call you from a number starting with one of the blocked prefixes (e.g. `+33 2 70 xx xx xx`). The call should be rejected.

## Next steps

- [Configuration](configuration.md) — all environment variables and CLI flags.
- [Reconciliation semantics](reconciliation.md) — strict normal vs additive degraded mode.
- [Docker](docker.md) — image details and Kubernetes notes.
- [Roadmap](roadmap.md) — what's planned and how to contribute.

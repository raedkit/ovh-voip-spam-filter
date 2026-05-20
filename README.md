# ovh-voip-spam-filter

Reconciles your OVH SIP incoming-blacklist with the [Saracroche](https://saracroche.org) community list (ARCEP démarchage prefixes + opérateurs réputés spam).

Two delivery modes:

- **Phase 1 — manual CSV** (`generate`): produces a file you import in the OVH Manager. Useful for first-time setup or quick experimentation. Fallback cascade live API → local cache → hard-coded ARCEP.
- **Phase 2 — API push** (`sync`): authenticates against OVH and reconciles the line state automatically, with rate-limit-aware throttling and 429 backoff. Designed to run non-interactively as a Docker container (and later as a Kubernetes CronJob).

Phase 3 backlog (K8s manifests, extra user blacklist, multi-line, etc.) lives in [docs/phase3-roadmap.md](docs/phase3-roadmap.md).

## Quickstart — manual CSV (Phase 1)

```bash
python -m ovh_spam_filter generate
# -> output/blocklist-ovh.csv
```

Then in the OVH Manager → Téléphonie → your SIP line → **Filtrage des appels** → **Importer** and select that CSV.

⚠️ The OVH UI can return **HTTP 429** on large CSV imports (it POSTs each row internally without throttling). If that happens, use the API push below — it's the same data, just delivered call-by-call with proper rate limiting.

## Quickstart — API push (Phase 2)

### 1. Generate an OVH token (once)

Open this URL — rules are pre-filled, choose unlimited validity for permanent personal use:

```
https://api.ovh.com/createToken/?GET=/me&GET=/telephony&GET=/telephony/*&GET=/telephony/*/screen&GET=/telephony/*/screen/*&GET=/telephony/*/screen/*/screenLists&GET=/telephony/*/screen/*/screenLists/*&PUT=/telephony/*/screen/*&POST=/telephony/*/screen/*/screenLists&DELETE=/telephony/*/screen/*/screenLists/*
```

OVH returns three values: `Application Key`, `Application Secret`, `Consumer Key`.

### 2. Discover your billing account and SIP line

```bash
docker run --rm \
  -e OVH_APPLICATION_KEY=... -e OVH_APPLICATION_SECRET=... -e OVH_CONSUMER_KEY=... \
  ovh-spam-filter:dev discover
```

Note the `billing_account` and `service_name` you want to target.

### 3. Dry-run

```bash
docker run --rm \
  -e OVH_APPLICATION_KEY=... -e OVH_APPLICATION_SECRET=... -e OVH_CONSUMER_KEY=... \
  -e OVH_BILLING_ACCOUNT=ab-12345-ovh -e OVH_SERVICE_NAME=0033xxxxxxxx \
  ovh-spam-filter:dev sync --dry-run
```

Prints the diff (to add / to remove / kept) and the estimated duration. No POST is sent.

### 4. Actual sync

```bash
docker run --rm \
  -e OVH_APPLICATION_KEY=... -e OVH_APPLICATION_SECRET=... -e OVH_CONSUMER_KEY=... \
  -e OVH_BILLING_ACCOUNT=ab-12345-ovh -e OVH_SERVICE_NAME=0033xxxxxxxx \
  ovh-spam-filter:dev sync
```

Bootstrap takes ~11 minutes at the default 1 req/s (643 entries). Subsequent runs only POST the changes — typically a few seconds.

### Build the image locally

```bash
docker build -t ovh-spam-filter:dev .
```

## Configuration

| Env var | Required | Default | Meaning |
|---|---|---|---|
| `OVH_ENDPOINT` | no | `ovh-eu` | `ovh-eu` / `ovh-ca` / `ovh-us` |
| `OVH_APPLICATION_KEY` | yes (sync/discover) | — | from `createToken` |
| `OVH_APPLICATION_SECRET` | yes (sync/discover) | — | from `createToken` |
| `OVH_CONSUMER_KEY` | yes (sync/discover) | — | from `createToken` |
| `OVH_BILLING_ACCOUNT` | yes (sync) | — | from `discover` |
| `OVH_SERVICE_NAME` | yes (sync) | — | from `discover` |
| `RATE_LIMIT_MS` | no | `1000` | min ms between API calls |
| `LOG_LEVEL` | no | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

For local CLI use, a `.ovh-credentials.json` file at the repo root is also supported (gitignored, takes lower priority than env vars):

```json
{
  "endpoint": "ovh-eu",
  "application_key": "...",
  "application_secret": "...",
  "consumer_key": "...",
  "billing_account": "ab-12345-ovh",
  "service_name": "0033xxxxxxxx"
}
```

## Reconciliation semantics

- **Normal mode** (Saracroche reachable): strict sync. POST the prefixes missing on OVH, DELETE the entries on OVH that are no longer in Saracroche. Manual entries you may have added through the OVH UI **will be deleted** (the reconciliation loop is the source of truth).
- **Degraded mode** (Saracroche unreachable): fall back to a hard-coded list of ARCEP démarchage prefixes (23 entries, 100% coverage of legal French telemarketing). **Additive-only — never deletes.** Partial knowledge could otherwise wipe out the rich list pushed during the last normal run.
- The mode is detected automatically — no flag.

## Commands

```bash
ovh-spam-filter generate [--output PATH] [--cache PATH] [--max-entries N] [--offline]
ovh-spam-filter status   [--cache PATH]
ovh-spam-filter discover
ovh-spam-filter sync     [--dry-run] [--rate-limit-ms N]
```

## CSV format (Phase 1)

OVH accepts three columns, comma-separated, prefixes allowed in `callNumber`:

```csv
callNumber,nature,type
+33162,international,incomingBlackList
+33270,international,incomingBlackList
```

`+33162` blocks every number starting with `01 62`.

## Why this works

Since 2022-09-01, the ARCEP reserved prefixes `01 62/63`, `02 70/71`, `03 77/78`, `04 24/25`, `05 68/69`, `09 48/49` exclusively to commercial telemarketing. Saracroche merges these with operator prefixes known for 100 % spam traffic. Blocking the union at the SIP line level neutralises virtually all *legal* French telemarketing.

## Rate limiting details

- Throttling is enforced **client-side** between every signed call.
- On 429 responses, the client respects the `Retry-After` header if present, otherwise applies a jittered exponential backoff (1, 2, 4, 8, 16, 30s, ±20% jitter, capped at 30s).
- After 3 consecutive 429s on the same session, the throttle interval is **doubled permanently** for the rest of the session (auto-adaptation — OVH's exact telephony quota is undocumented and may be stricter than the 60 req/min advertised for Public Cloud).

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest      # 55 tests
.venv/bin/python -m ovh_spam_filter generate
```

## License

GPLv3 (matches Saracroche, whose data we redistribute).

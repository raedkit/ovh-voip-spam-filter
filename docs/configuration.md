# Configuration

All configuration is done via **environment variables**. The CLI also accepts flags that override the env vars for one-off runs.

## Environment variables

| Variable | Required for | Default | Description |
|---|---|---|---|
| `OVH_ENDPOINT` | sync, discover | `ovh-eu` | `ovh-eu`, `ovh-ca`, or `ovh-us` |
| `OVH_APPLICATION_KEY` | sync, discover | — | Application key from `createToken` |
| `OVH_APPLICATION_SECRET` | sync, discover | — | Application secret from `createToken` |
| `OVH_CONSUMER_KEY` | sync, discover | — | Consumer key from `createToken` |
| `OVH_BILLING_ACCOUNT` | sync | — | The billing account to target (from `discover`) |
| `OVH_SERVICE_NAME` | sync | — | The SIP line to target (from `discover`) |
| `RATE_LIMIT_MS` | — | `1000` | Min milliseconds between API calls |
| `LOG_LEVEL` | — | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |

## Local development convenience: `.ovh-credentials.json`

When running locally (not in Docker / K8s), you can keep your credentials in a JSON file at the repo root. It's gitignored by default:

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

Precedence: **CLI flag > env var > `.ovh-credentials.json` > built-in default**.

The file is `chmod 600` automatically when written by the code.

## CLI flags

- `sync --dry-run` — show the plan without applying it.
- `sync --rate-limit-ms N` — override the throttle interval for this run.
- `generate --output PATH` — write CSV to a custom path.
- `generate --offline` — skip the network, use cache or ARCEP fallback only.
- `generate --max-entries N` — truncate to N rows (legacy, for OVH CSV import workarounds).

Run any subcommand with `--help` for the full list.

## Kubernetes setup

The intended deployment model is a `CronJob` running `sync` weekly or daily. The image runs as a non-root user (UID 10001) and accepts all configuration via env vars, so a typical Pod spec is:

```yaml
envFrom:
  - secretRef:
      name: ovh-credentials      # contains OVH_APPLICATION_KEY/SECRET/CONSUMER_KEY
  - configMapRef:
      name: ovh-spam-config      # contains OVH_BILLING_ACCOUNT, OVH_SERVICE_NAME, etc.
```

See the [roadmap](roadmap.md) for upcoming ready-to-use manifests under `deploy/k8s/`.

## Network considerations

- Saracroche API: `GET https://saracroche.org/api/v1/lists/french-list-arcep-operators` — single ~150 KB JSON fetch per run.
- OVH API: `https://{endpoint}.api.ovh.com/1.0/telephony/...` — N small requests, throttled by `RATE_LIMIT_MS`.

If your egress is filtered, allowlist both hosts.

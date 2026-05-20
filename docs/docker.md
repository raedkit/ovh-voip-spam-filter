# Docker

The image is published to **GitHub Container Registry** at `ghcr.io/raedkit/ovh-voip-spam-filter`.

## Tags

- `:latest` — the most recent stable release
- `:v0.2.0` — exact version
- `:0.2` — minor track (auto-updates within 0.2.x)
- `:0` — major track (auto-updates within 0.x.y)

Multi-arch: **linux/amd64** and **linux/arm64**. The image works on Apple Silicon, ARM Kubernetes clusters, and Raspberry Pi.

## Pull and run

```bash
docker pull ghcr.io/raedkit/ovh-voip-spam-filter:latest

docker run --rm \
  -e OVH_APPLICATION_KEY=... \
  -e OVH_APPLICATION_SECRET=... \
  -e OVH_CONSUMER_KEY=... \
  -e OVH_BILLING_ACCOUNT=ab-12345-ovh \
  -e OVH_SERVICE_NAME=0033xxxxxxxx \
  ghcr.io/raedkit/ovh-voip-spam-filter:latest sync
```

Use `--env-file` for cleanliness:

```bash
cat > ovh.env <<EOF
OVH_APPLICATION_KEY=...
OVH_APPLICATION_SECRET=...
OVH_CONSUMER_KEY=...
OVH_BILLING_ACCOUNT=ab-12345-ovh
OVH_SERVICE_NAME=0033xxxxxxxx
EOF
chmod 600 ovh.env

docker run --rm --env-file ovh.env ghcr.io/raedkit/ovh-voip-spam-filter:latest sync
```

## Image details

- Base: `python:3.12-slim`
- Multi-stage build (builder + runtime)
- Runs as **non-root** user `ovh` (UID `10001`)
- Entrypoint: `python -m ovh_voip_spam_filter`
- Default command: `sync`
- `PYTHONUNBUFFERED=1` so logs flush immediately to stderr
- No mounted volumes required — the container is fully ephemeral

## Building locally

```bash
git clone https://github.com/raedkit/ovh-voip-spam-filter.git
cd ovh-voip-spam-filter
docker build -t ovh-voip-spam-filter:dev .
docker run --rm ovh-voip-spam-filter:dev --help
```

## Kubernetes CronJob (sketch)

A future release will ship `deploy/k8s/` templates. For now, a minimal CronJob looks like:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ovh-voip-spam-filter
spec:
  schedule: "0 3 * * 1"           # Monday 03:00 UTC
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      activeDeadlineSeconds: 1800  # absorb a 13-min bootstrap with margin
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: sync
              image: ghcr.io/raedkit/ovh-voip-spam-filter:latest
              args: ["sync"]
              envFrom:
                - secretRef:    { name: ovh-credentials }
                - configMapRef: { name: ovh-spam-config }
```

See the [roadmap](roadmap.md) for ready-to-deploy manifests.

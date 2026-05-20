# Roadmap & ideas

This project is intentionally a small core (CLI + reconcile loop) with optional extensions. The ideas below are stretch goals — contributions welcome. None of them are promised deliverables.

If something here matches a need you have, open an issue (or a PR) — happy to discuss design before code.

## Kubernetes manifests

Make the existing Docker image trivial to deploy as a CronJob.

- `deploy/k8s/cronjob.yaml` with sensible defaults (`concurrencyPolicy: Forbid`, `restartPolicy: OnFailure`, `activeDeadlineSeconds: 1800` to absorb a bootstrap run, `successfulJobsHistoryLimit: 3`).
- `deploy/k8s/secret-template.yaml` for the 3 OVH credentials.
- `deploy/k8s/configmap.yaml` for `OVH_ENDPOINT`, `OVH_BILLING_ACCOUNT`, `OVH_SERVICE_NAME`, `RATE_LIMIT_MS`.
- Optional kustomize overlay for multi-cluster setups.

## Personal blocklist overlay

Let users pin extra numbers that aren't (or shouldn't be) in Saracroche:

- Env var `EXTRA_CALL_NUMBERS="+33612345678,+33170,+33780"` (comma-separated), or
- Mounted file `EXTRA_CALL_NUMBERS_FILE=/etc/ovh-voip-spam-filter/extra.txt` (one prefix per line, `#` for comments).
- Pipeline: `target = saracroche_patterns ∪ extra_patterns` before the diff.
- In degraded mode: `target = arcep_hardcoded ∪ extra_patterns` (personal entries are kept).
- Test must enforce that any `EXTRA_CALL_NUMBERS` entry appears in the resulting sync no matter the source mode.

## Observability — Prometheus metrics

Useful for users running `sync` on a schedule and wanting alerts on regressions.

- `ovh_voip_spam_filter_run_total{result="success|degraded|failed"}` (counter)
- `ovh_voip_spam_filter_run_duration_seconds` (histogram)
- `ovh_voip_spam_filter_posts_total`, `..._deletes_total`, `..._retries_total` (counters)
- `ovh_voip_spam_filter_last_success_timestamp_seconds` (gauge)
- `ovh_voip_spam_filter_saracroche_patterns_count`, `..._ovh_entries_count` (gauges)
- `ovh_voip_spam_filter_429_total` (counter — useful to calibrate the throttle)

For a short-lived Job, a Prometheus **Pushgateway** is probably more appropriate than an HTTP endpoint.

## Automatic spam detection from OVH call logs

Surface new spammers we don't block yet by looking at the line's incoming history:

- Read `/telephony/{ba}/line/{sn}/incomingMcps` for the last N days.
- Heuristics (very short duration, no answer, geographic ranges not yet flagged, recurrence).
- Forward candidates to Saracroche via `POST https://saracroche.org/api/v1/reports` (auth TBD with the Saracroche maintainer).
- Cooldown so the same number isn't reported repeatedly.

Privacy is the main constraint — the call logs contain caller numbers, so this needs to stay opt-in and well-documented.

## Multi-line support

Some users have several SIP lines on the same billing account.

- Env var `OVH_SERVICE_NAMES="line1,line2,line3"` instead of the singular form.
- Same target list applied to each line in sequence.
- Per-line logs and result aggregates.

## Tracking managed-vs-manual entries

Today, the strict-sync mode deletes anything that isn't in Saracroche, including entries the user might have added manually via the OVH UI. If preserving manual entries becomes a need:

- Persist the previous Saracroche snapshot in a PVC.
- On the next run, `to_remove = previous_saracroche - current_saracroche` rather than `current_ovh - current_saracroche`.
- Entries in `current_ovh` but in neither `previous` nor `current` are inferred as manual and left alone.

This trades some infra dependency for the comfort of co-existence. Probably worth it only if the user actually adds entries manually.

## Multi-target (multiple OVH accounts)

If the same person manages multiple OVH accounts (perso + pro for instance), let one run push to several profiles:

- `OVH_PROFILES="perso,pro"` then per-profile env vars `OVH_PERSO_APPLICATION_KEY=...`, `OVH_PRO_APPLICATION_KEY=...`, etc.
- Alternatively (and probably simpler): run the container N times with N env files. No code change needed.

## Improvements considered

- **Structured JSON logs**: trivial to add as a `LOG_FORMAT=json` toggle for Loki / ELK consumption.
- **Dry-run JSON output**: `sync --dry-run --output json` for piping to other tools.
- **GitHub release notes** with screenshots of the resulting OVH manager view.

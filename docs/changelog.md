# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-05-20

First public release.

### Added

- `sync` CLI command — reconciles the OVH SIP blacklist with the Saracroche community list via the OVH API, with client-side throttling (default 1 req/s) and 429-aware backoff.
- `discover` CLI command — lists OVH billing accounts and screen-capable SIP lines.
- `generate` CLI command (legacy) — produces a CSV for manual import via the OVH Manager UI, with cascade fallback (Saracroche live → local cache → hard-coded ARCEP prefixes).
- `status` CLI command — inspects local cache freshness and Saracroche API reachability.
- OVH signed-request client (`$1$` SHA-1 scheme), stdlib only.
- Reconciliation modes:
  - **Normal** (Saracroche reachable): strict sync — adds missing prefixes and deletes prefixes no longer in Saracroche.
  - **Degraded** (Saracroche unreachable): falls back to hard-coded ARCEP prefixes, additive-only (never deletes — anti-regression).
- Auto-promotion of `incomingScreenList=disabled` to `blacklist` with a WARN log, preserving `outgoing`.
- Auto-adaptation of throttle interval after 3 consecutive 429 responses.
- Per-call progress counter in `sync` logs (`Added +33162 (1/643)`).
- Docker image (multi-stage `python:3.12-slim`, non-root UID 10001), entrypoint `ovh-voip-spam-filter sync`, published to GitHub Container Registry.
- PyPI distribution — `pip install ovh-voip-spam-filter`.
- Bilingual documentation (English + French) via README files and a full MkDocs Material site deployed to GitHub Pages.
- GitHub Actions CI (lint with ruff, type-check with mypy, tests with pytest on Python 3.12 + 3.13, Docker build for `linux/amd64` and `linux/arm64`).
- GitHub Actions Release workflow (Docker push to GHCR + PyPI publish via Trusted Publisher OIDC + GitHub Release with changelog excerpt).
- Renovate configuration for weekly dependency updates.
- Repo hygiene: `LICENSE` (GPL-3.0-or-later), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SECURITY.md`, issue and PR templates.

### Acknowledgments

This release would not exist without [Saracroche](https://saracroche.org) by [Camille Bouvat](https://github.com/cbouvat) — the community-maintained blocklist of ~16 million numbers we consume.

[Unreleased]: https://github.com/raedkit/ovh-voip-spam-filter/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/raedkit/ovh-voip-spam-filter/releases/tag/v0.2.0

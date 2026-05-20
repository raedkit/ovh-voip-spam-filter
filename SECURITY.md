# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability — credentials handling, OVH API request signing, supply-chain weakness, or any flaw that could compromise a user's telephony account — **please do not open a public issue**.

Instead:

1. Use GitHub's [private vulnerability reporting](https://github.com/raedkit/ovh-voip-spam-filter/security/advisories/new) on this repository, **or**
2. Email the maintainer directly (see the GitHub profile linked from this repository).

You should receive an acknowledgement within **72 hours**. A fix or mitigation will be discussed and released within **90 days** for confirmed vulnerabilities.

## Scope

In scope:

- Bugs in the OVH `$1$` SHA-1 request signing that could leak credentials or be replayed
- Mishandling of `.ovh-credentials.json` (permissions, accidental logging, accidental commits)
- Dependency vulnerabilities affecting this project's runtime
- Container image misconfigurations (root user, unnecessary capabilities, embedded secrets)

Out of scope:

- Bugs in OVH's own API or infrastructure — report those to OVHcloud directly
- Issues with Saracroche's source list — report those to the [Saracroche project](https://saracroche.org)
- Phone-number spam classification false positives/negatives — those are Saracroche-side concerns

## Credentials best practices

- Store credentials in environment variables or Kubernetes Secrets, never commit them.
- The `.ovh-credentials.json` file is gitignored by default — verify before committing in forks.
- Generate OVH tokens via the URL provided in the README (which restricts them to the minimum required scopes).
- Rotate tokens periodically. If a token is ever exposed (logs, screenshots, chat sessions), revoke it immediately at <https://eu.api.ovh.com/me/api/credential>.

Thanks for helping keep users safe.

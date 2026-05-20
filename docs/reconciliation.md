# Reconciliation semantics

The `sync` command runs a reconciliation loop : it reads the current OVH state, diffs it against the target (Saracroche, or the hard-coded ARCEP fallback), and applies the difference.

The behavior is **mode-dependent**:

## Normal mode (Saracroche reachable)

Saracroche is the source of truth.

- `to_add = target − current` — POST every prefix that should be present but isn't.
- `to_remove = current − target` — DELETE every entry that's on OVH but not in Saracroche.

This is **strict sync**. If Saracroche removes a prefix (community correction, e.g. a range that was too broad), the next run propagates that removal to OVH.

!!! warning "Manual UI entries are deleted in this mode"
    If you've added entries directly in the OVH Manager UI, **they will be removed** at the next `sync`, because they're not in Saracroche. This is intentional: the reconciliation loop owns the line's blacklist.

    If preserving manual entries matters to you, see the [roadmap](roadmap.md#personal-blocklist-overlay) for the planned `EXTRA_CALL_NUMBERS` overlay (env var) — it'll let you union extras with Saracroche.

## Degraded mode (Saracroche unreachable)

When Saracroche's API fails, the tool falls back to a hard-coded list of **23 ARCEP démarchage prefixes** built into the package. These cover 100% of legally-mandated French telemarketing ranges.

- `to_add = arcep − current` — POST any missing ARCEP prefix.
- `to_remove = []` — **never delete**, no matter what's on OVH.

The additive-only behavior is critical. Without it, a transient Saracroche outage would wipe ~620 entries (the difference between Saracroche's rich list and the 23 ARCEP prefixes), causing a major regression. The tool errs on the side of preserving what's there.

`sync` logs the mode at startup:

```text
[WARNING] Saracroche unreachable (timeout) — degraded mode with hard-coded ARCEP
```

## Auto-promoting `disabled` to `blacklist`

If your line's `incomingScreenList` is set to `disabled`, the entries added by `sync` would have no effect. The tool detects this at startup and auto-promotes to `blacklist`, preserving `outgoingScreenList` :

```text
[WARNING] Screen state: incoming=disabled outgoing=disabled — auto-activating incoming=blacklist (preserving outgoing=disabled)
```

This is a side effect, but designed to be safe: it only flips the incoming policy from "disabled" to "blacklist", which is the only state where the blacklist actually filters.

## Throttling and 429

- Client-side throttle: `RATE_LIMIT_MS` (default `1000` = 1 req/s) is enforced between every signed call.
- On `HTTP 429`:
  - The `Retry-After` header is respected if present.
  - Otherwise, an exponential backoff with ±20% jitter is used: 1, 2, 4, 8, 16, 30s (capped).
- After **3 consecutive 429s**, the throttle interval is **doubled permanently** for the rest of the session (auto-adaptation). The new interval is logged.

The default 1 req/s is well below OVH's documented 60 req/min ceiling for Public Cloud, and matches what was observed in practice on telephony endpoints.

## Idempotency

`sync` is fully idempotent. Two consecutive runs without external changes will result in `added=0 removed=0 failed=0`. The second run is the verification of the first.

## Exit codes

- `0` — converged successfully (or partially, with non-fatal failures — the next run will retry).
- `1` — fatal error: auth failure, all retries exhausted on critical calls, etc.

In a CronJob, exit code `0` even on partial failure is intentional. Kubernetes won't restart a Job that exits `0`, and the next scheduled run will pick up where it left off.

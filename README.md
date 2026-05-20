# ovh-voip-spam-filter

Generate a blocklist CSV for the OVH VoIP/SIP incoming call filter, sourced from the [Saracroche](https://saracroche.org) community list (ARCEP démarchage prefixes + opérateurs réputés spam).

Phase 1 produces a file you import manually in the OVH Manager. Phase 2 (later) will push the diff via the OVH API and run on a cron.

## Quickstart

```bash
python -m ovh_spam_filter generate
# -> output/blocklist-ovh.csv
```

Then in the OVH Manager → Téléphonie → your SIP line → **Filtrage des appels** → **Importer** and select that CSV. Activate the incoming blacklist on the line if not already active.

## Commands

```bash
python -m ovh_spam_filter generate [--output PATH] [--max-entries N] [--offline]
python -m ovh_spam_filter status
```

- `generate` — fetch Saracroche, write the CSV. Cascade: live API → local cache (`cache/saracroche-latest.json`) → hard-coded ARCEP prefixes.
  - `--max-entries N` — truncate to N rows (ARCEP first), used if the OVH UI rejects large imports.
  - `--offline` — skip the network, use cache only.
- `status` — show cache freshness and API reachability.

## CSV format

OVH accepts three columns, comma-separated, prefixes allowed in `callNumber`:

```csv
callNumber,nature,type
+33162,international,incomingBlackList
+33270,international,incomingBlackList
```

`+33162` blocks every number starting with `01 62`.

## Why this works

Since 2022-09-01, the ARCEP reserved prefixes `01 62/63`, `02 70/71`, `03 77/78`, `04 24/25`, `05 68/69`, `09 48/49` exclusively to commercial telemarketing. Saracroche merges these with operator prefixes known for 100 % spam traffic. Blocking the union at the SIP line level neutralises virtually all *legal* French telemarketing.

## License

GPLv3 (matches Saracroche, whose data we redistribute).

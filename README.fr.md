<div align="center">

# ovh-voip-spam-filter

[🇬🇧 English](README.md) · 🇫🇷 **Français**

**Synchronise la liste noire entrante de ta ligne SIP OVH avec [Saracroche](https://saracroche.org), la blocklist communautaire de ~16 millions de numéros de démarchage français.**

[![CI](https://github.com/raedkit/ovh-voip-spam-filter/actions/workflows/ci.yml/badge.svg)](https://github.com/raedkit/ovh-voip-spam-filter/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/raedkit/ovh-voip-spam-filter?display_name=tag&sort=semver)](https://github.com/raedkit/ovh-voip-spam-filter/releases)
[![GHCR](https://img.shields.io/badge/ghcr.io-ovh--voip--spam--filter-blue?logo=docker)](https://github.com/raedkit/ovh-voip-spam-filter/pkgs/container/ovh-voip-spam-filter)
[![PyPI](https://img.shields.io/pypi/v/ovh-voip-spam-filter)](https://pypi.org/project/ovh-voip-spam-filter/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-green)](LICENSE)

📖 **Documentation complète : [raedkit.github.io/ovh-voip-spam-filter/fr/](https://raedkit.github.io/ovh-voip-spam-filter/fr/)**

</div>

---

> [!WARNING]
> **Utilise l'API (`sync`), pas le CSV.**
> L'import CSV du Manager OVH **échoue au-delà de ~80 entrées** (constaté empiriquement). Ce projet existe pour pousser les mêmes données via l'API OVH un préfixe à la fois, throttlé et idempotent. Le mode CSV reste disponible pour dépannage mais **n'est pas** le chemin recommandé.

## Démarrage rapide

```bash
docker run --rm \
  -e OVH_APPLICATION_KEY=... \
  -e OVH_APPLICATION_SECRET=... \
  -e OVH_CONSUMER_KEY=... \
  -e OVH_BILLING_ACCOUNT=... \
  -e OVH_SERVICE_NAME=... \
  ghcr.io/raedkit/ovh-voip-spam-filter:latest sync
```

Ou via PyPI :

```bash
pip install ovh-voip-spam-filter
ovh-voip-spam-filter sync
```

Génère un token OVH avec [cette URL préremplie](https://api.ovh.com/createToken/?GET=/me&GET=/telephony&GET=/telephony/*&GET=/telephony/*/screen&GET=/telephony/*/screen/*&GET=/telephony/*/screen/*/screenLists&GET=/telephony/*/screen/*/screenLists/*&PUT=/telephony/*/screen/*&POST=/telephony/*/screen/*/screenLists&DELETE=/telephony/*/screen/*/screenLists/*) (permissions minimales pré-cochées).

Walkthrough complet : **[docs/démarrage rapide](https://raedkit.github.io/ovh-voip-spam-filter/fr/quickstart/)**.

## Pourquoi cet outil

Le Manager OVH propose un import CSV pour la liste noire entrante, mais il POSTe chaque ligne en interne sans rate-limiting. La liste Saracroche fait **643 préfixes** — l'import OVH renvoie un HTTP 429 après ~80. Cet outil fait le même boulot proprement : requêtes API signées, throttle côté client, backoff exponentiel sur 429, auto-adaptation si OVH durcit le quota. Le bootstrap prend ~13 minutes ; les runs suivants sont idempotents et durent quelques secondes.

## Comment ça marche

```
            ┌────────────────────────────┐
            │  API Saracroche live       │
            │  (~643 préfixes block-only)│
            └─────────────┬──────────────┘
                          │  fallback si down
                          ▼
            ┌────────────────────────────┐
            │  Fallback ARCEP en dur     │
            │  (23 préfixes, additif)    │
            └─────────────┬──────────────┘
                          ▼
            ┌────────────────────────────┐
            │  Diff vs état OVH actuel   │
            │  (réconciliation GET-first)│
            └─────────────┬──────────────┘
                          ▼
            ┌────────────────────────────┐
            │  Push API OVH signé        │
            │  (throttlé, 429-aware)     │
            └────────────────────────────┘
```

- **Mode normal** (Saracroche joignable) — sync strict : ajoute les préfixes manquants, retire ceux que Saracroche a retirés.
- **Mode dégradé** (Saracroche injoignable) — utilise le fallback ARCEP en dur, **additif uniquement**, ne supprime jamais. Garantie anti-régression.

Détails : **[sémantique de réconciliation](https://raedkit.github.io/ovh-voip-spam-filter/fr/reconciliation/)**.

## Remerciements

🙏 **Ce projet n'existerait pas sans [Saracroche](https://saracroche.org), créé par [Camille Bouvat](https://github.com/cbouvat).**

Saracroche est une blocklist open source communautaire de ~16 millions de numéros de démarchage et de spam français, maintenue en solo et bénévolement depuis 2020. On consomme l'endpoint [`french-list-arcep-operators`](https://saracroche.org/api/v1/lists/french-list-arcep-operators) comme source de vérité primaire, sans cache côté redistribution — la fraîcheur que tu obtiens est exactement celle que Saracroche a en ce moment.

Si cet outil t'a évité un appel spam, **soutiens Camille** :

- 💛 [Liberapay](https://liberapay.com/cbouvat) (préféré)
- 💳 [Stripe / don ponctuel](https://saracroche.org)
- 🐙 [GitHub Sponsors](https://github.com/cbouvat)

Saracroche en source :

- 📱 Apps : [iOS](https://apps.apple.com/fr/app/saracroche/id6743679292) · [Android](https://play.google.com/store/apps/details?id=com.cbouvat.android.saracroche)
- 🦊 Code : [Codeberg (android)](https://codeberg.org/cbouvat/saracroche-android) · [GitHub (legacy)](https://github.com/cbouvat)

## Documentation

Doc complète sur **[raedkit.github.io/ovh-voip-spam-filter/fr/](https://raedkit.github.io/ovh-voip-spam-filter/fr/)** :

- [Démarrage rapide](https://raedkit.github.io/ovh-voip-spam-filter/fr/quickstart/) — token, discover, sync
- [Configuration](https://raedkit.github.io/ovh-voip-spam-filter/fr/configuration/) — env vars, flags CLI, Kubernetes
- [Docker](https://raedkit.github.io/ovh-voip-spam-filter/fr/docker/) — détails image, multi-arch, CronJob
- [PyPI](https://raedkit.github.io/ovh-voip-spam-filter/fr/pypi/) — install + usage librairie
- [Réconciliation](https://raedkit.github.io/ovh-voip-spam-filter/fr/reconciliation/)
- [Référence API](https://raedkit.github.io/ovh-voip-spam-filter/fr/api-reference/)
- [Feuille de route](https://raedkit.github.io/ovh-voip-spam-filter/fr/roadmap/)

## Contribuer

PRs bienvenus. Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour le setup et la checklist PR. En participant, tu acceptes le [Code of Conduct](CODE_OF_CONDUCT.md).

Vulnérabilités : voir [SECURITY.md](SECURITY.md). N'ouvre pas d'issue publique pour les bugs liés aux credentials.

## License

[GPL-3.0-or-later](LICENSE) — en cohérence avec Saracroche.

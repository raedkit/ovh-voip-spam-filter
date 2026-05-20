# ovh-voip-spam-filter

Synchronise la **liste noire entrante de ta ligne SIP OVH** avec [**Saracroche**](https://saracroche.org), la blocklist communautaire de ~16 millions de numéros de démarchage téléphonique français.

!!! warning "Utilise l'API, pas le CSV"
    L'import CSV via le Manager OVH **échoue au-delà de ~80 entrées** (constaté empiriquement). Ce projet existe pour pousser les mêmes données via l'API OVH, throttlée à un rythme sûr, avec une réconciliation idempotente et un backoff sur 429. Le mode CSV reste disponible pour dépannage mais **n'est pas** le chemin recommandé.

## Ce que ça fait

- Récupère la [liste live Saracroche](https://saracroche.org/api/v1/lists/french-list-arcep-operators) (~643 préfixes block-only couvrant 16M+ numéros).
- Pousse le diff vers la liste noire entrante de ta ligne SIP OVH via l'API OVH signée, un préfixe à la fois, throttlé à 1 req/s par défaut.
- Réconciliation stricte en mode normal : ajoute ce qui manque **et** retire ce que Saracroche a retiré.
- Anti-régression : en mode dégradé (Saracroche injoignable), bascule sur une liste codée en dur de 23 préfixes ARCEP et fonctionne en **mode additif uniquement** — ne supprime jamais.
- Active automatiquement `incomingScreenList=blacklist` avec un log WARN si la ligne est en `disabled`.

## Distribution

Disponible via :

- **Image Docker** : `ghcr.io/raedkit/ovh-voip-spam-filter:latest` (multi-arch amd64 + arm64, ~216 Mo)
- **Package PyPI** : `pip install ovh-voip-spam-filter`

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

Voir [Démarrage rapide](quickstart.md) pour le walkthrough complet avec génération du token OVH.

## Remerciements

Ce projet n'existerait pas sans [**Saracroche**](https://saracroche.org), une blocklist open source communautaire créée et maintenue par [**Camille Bouvat**](https://github.com/cbouvat) — en solo, sur son temps libre, entièrement open source sous GPL-3.0, sans pubs et sans paywall. La liste contient ~16 millions de numéros utilisés par les démarcheurs commerciaux français et les opérateurs spam, mise à jour quotidiennement.

On consomme l'endpoint `french-list-arcep-operators` de Saracroche comme source de vérité primaire. **Si cet outil t'a évité un appel spam, fais un [don à Camille](https://liberapay.com/cbouvat) ou via [Stripe sur saracroche.org](https://saracroche.org)**.

- Apps et code Saracroche : [Codeberg](https://codeberg.org/cbouvat/saracroche-android) · [GitHub](https://github.com/cbouvat)

## License

GPL-3.0-or-later, en cohérence avec Saracroche.

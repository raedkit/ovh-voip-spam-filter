# Phase 3 — Roadmap et brainstorming (hors scope Phase 2)

Ce document préserve les discussions et décisions hors-scope pour ne pas les perdre. Il vise à servir de point de départ quand on lancera Phase 3.

Phase 1 (CSV manuel) est sur `main`. Phase 2 (sync API + Docker) est sur `feat/ovh-api-throttled` et concerne uniquement la livraison "image Docker non-interactive". Phase 3 ajoute les éléments ci-dessous.

## 1. Déploiement Kubernetes

**Objectif** : faire tourner la commande `sync` en `CronJob` quotidien ou hebdomadaire.

Livrables attendus :
- `deploy/k8s/cronjob.yaml` (ou kustomize) avec :
  - `schedule: "0 3 * * 1"` (lundi 3h UTC, low-traffic) — à confirmer
  - `concurrencyPolicy: Forbid` (un seul reconcile en cours à la fois)
  - `restartPolicy: OnFailure` (laisser K8s retry à l'intérieur du Job avant de tenter le prochain schedule)
  - `activeDeadlineSeconds: 1800` minimum (absorbe un bootstrap de ~11 min + marge)
  - `successfulJobsHistoryLimit: 3`, `failedJobsHistoryLimit: 3`
- `deploy/k8s/secret-template.yaml` : template `kind: Secret` pour les 3 credentials OVH (AK / AS / CK) — usage `kubectl create secret generic ovh-creds --from-literal=...`
- `deploy/k8s/configmap.yaml` : `OVH_ENDPOINT`, `OVH_BILLING_ACCOUNT`, `OVH_SERVICE_NAME`, `RATE_LIMIT_MS`
- Documentation : comment publier l'image (registry de l'utilisateur, ghcr.io ou docker hub), comment rotater le token, comment monitorer l'historique des Jobs

Points ouverts :
- Schedule : quotidien (`0 3 * * *`) vs hebdo (`0 3 * * 1`). Saracroche met à jour quotidiennement mais l'évolution typique d'un run sur l'autre est faible. Hebdo suffit pour 99% des cas. Quotidien si l'utilisateur veut un signalement plus réactif.
- Stratégie de publication d'image : GitHub Actions sur push de tag → ghcr.io ? Ou build manuel local ?

## 2. Extra blacklist utilisateur (overlay personnel)

**Demande explicite du user** : un mode où l'utilisateur fournit sa propre liste additionnelle de numéros qui sont mergés avec Saracroche avant le sync. Permet de pinner des numéros personnels (entreprises locales qui spamment, anciens spammeurs non identifiés par Saracroche, etc.) sans modifier le code ni passer par l'UI OVH (où le sync strict les supprimerait).

Design proposé :
- Env var `EXTRA_CALL_NUMBERS="+33612345678,+33170,+33780"` (liste séparée par virgule)
- OU fichier monté : `EXTRA_CALL_NUMBERS_FILE=/etc/ovh-spam-filter/extra.txt` (un préfixe ou numéro par ligne, `#` commentaires)
- Pipeline : `target = saracroche_patterns ∪ extra_patterns` → diff → apply
- Préfixes utilisateur prioritaires en cas de conflit (ils sont ARCEP-equivalent pour la priorisation)
- En mode dégradé : `target = arcep_hardcoded ∪ extra_patterns` (les extras sont *plus* fiables que Saracroche, donc on les inclut quand même)
- Test obligatoire : un `EXTRA_CALL_NUMBERS` non vide doit toujours figurer dans le CSV / le sync result, peu importe le mode

Format `callNumber` toléré : préfixe partiel comme dans Saracroche (`+33170` bloque tout 01 70 xx xx xx).

## 3. Métriques Prometheus / observabilité

Pour intégrer dans un dashboard et alerter en cas de régression :

- `ovh_spam_filter_run_total{result="success|degraded|failed"}` (counter)
- `ovh_spam_filter_run_duration_seconds` (histogram)
- `ovh_spam_filter_posts_total`, `..._deletes_total`, `..._retries_total` (counter)
- `ovh_spam_filter_last_success_timestamp_seconds` (gauge)
- `ovh_spam_filter_saracroche_patterns_count`, `..._ovh_entries_count` (gauge)
- `ovh_spam_filter_429_total` (counter, pour calibrer le rate-limit)

Implémentation : `prometheus_client` Python (1 dépendance) OU push gateway si on veut éviter d'exposer un endpoint dans un Job (qui ne tourne pas longtemps).

Pour un Job K8s : push gateway est probablement la bonne option.

## 4. Détection automatique de nouveaux spams via call logs OVH

Pipeline avancé : surveiller les appels entrants reçus, identifier ceux qu'on n'a pas bloqués mais qui ressemblent à du spam, les signaler automatiquement à Saracroche.

- `GET /telephony/{ba}/line/{sn}/incomingMcps` : logs d'appels entrants des derniers jours
- Heuristique de détection :
  - Durée < 5s ET pas répondu (probable robocall)
  - Numéro appelant dans une plage suspecte non encore signalée
  - Fréquence élevée du même numéro
- `POST https://saracroche.org/api/v1/reports` : signaler le numéro (avec auth Saracroche si requise)
- Cooldown : ne pas re-signaler le même numéro dans les 30 jours

Risques :
- Faux positifs (rappels légitimes courts)
- Confidentialité (les logs contiennent les numéros appelants)

Probablement à isoler dans un service distinct du sync.

## 5. Multi-line support

L'utilisateur peut avoir plusieurs lignes SIP sur le même billing account.

Design :
- `OVH_SERVICE_NAMES="line1,line2,line3"` au lieu de `OVH_SERVICE_NAME` unique
- Le sync boucle, applique le même target à chaque ligne
- Logs identifient clairement quelle ligne est en cours

## 6. PVC pour distinguer "managed by sync" vs "manuel UI"

Trade-off acté en Phase 2 : les entrées manuelles ajoutées via l'UI OVH sont supprimées au prochain sync en mode normal (sync strict). Si ce comportement devient gênant en pratique, on peut le résoudre via un PVC :

- À chaque sync réussi, écrire dans le PVC `previous-saracroche-snapshot.json` (la liste exacte des patterns que nous avons pushés)
- Au sync suivant, le diff devient :
  - `to_add = current_saracroche - current_ovh`
  - `to_remove = previous_saracroche - current_saracroche` (au lieu de `current_ovh - current_saracroche`)
- Ce qui n'est ni dans `previous` ni dans `current` est considéré comme manuel → préservé
- Update `previous = current_saracroche` à la fin

Coût : 1 PVC ReadWriteOnce, persistance entre runs.
Bénéfice : cohabitation avec des entrées manuelles préservées.

À ne déclencher que si le besoin émerge clairement.

## 7. Mode multi-cible (multi-comptes OVH)

Si l'utilisateur a plusieurs comptes OVH (perso + pro par exemple), pousser la même blocklist sur les deux en un seul run.

Design : factoriser les credentials par "profil" :
```
OVH_PROFILES="perso,pro"
OVH_PERSO_APPLICATION_KEY=...
OVH_PERSO_SERVICE_NAME=0033...
OVH_PRO_APPLICATION_KEY=...
OVH_PRO_SERVICE_NAME=0033...
```

Risque : explosion de la matrice de config. Peut-être préférer de lancer le container N fois avec N env files.

## 8. Améliorations diverses notées

- **Format JSON pour les logs** : si l'utilisateur intègre dans Loki / ELK / etc., un formatter JSON serait apprécié. Trivial à ajouter (basé sur la stdlib `logging`).
- **Healthcheck Docker** : pour un Job, healthcheck inutile (le Job complète ou échoue). Mais utile si un jour on transforme `sync` en daemon avec sleep entre runs.
- **Dry-run en JSON** : `sync --dry-run --output json` pour piping dans d'autres outils.
- **CI GitHub Actions** : build image sur tag, push ghcr.io, tests.

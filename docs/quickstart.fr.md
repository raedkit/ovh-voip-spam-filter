# Démarrage rapide

Ce guide te fait passer de zéro à un `sync` fonctionnel contre ta ligne SIP OVH en ~10 minutes (plus ~13 min de bootstrap pour le premier sync).

## Prérequis

- Une ligne VoIP/SIP OVH active accessible depuis le [Manager OVH](https://www.ovh.com/manager/).
- **Docker** (recommandé) ou **Python 3.12+** + `pip`.

## 1. Générer un token OVH

Ouvre [cette URL `createToken` préremplie](https://api.ovh.com/createToken/?GET=/me&GET=/telephony&GET=/telephony/*&GET=/telephony/*/screen&GET=/telephony/*/screen/*&GET=/telephony/*/screen/*/screenLists&GET=/telephony/*/screen/*/screenLists/*&PUT=/telephony/*/screen/*&POST=/telephony/*/screen/*/screenLists&DELETE=/telephony/*/screen/*/screenLists/*) — elle demande le minimum de permissions nécessaire.

1. Connecte-toi avec ton compte OVH.
2. Choisis la durée de validité (**Illimitée** pour usage perso permanent, ou **1 an** avec rotation manuelle).
3. Clique sur **Créer les clefs**.
4. Récupère les trois valeurs : `Application Key`, `Application Secret`, `Consumer Key`. Garde-les en sécurité.

!!! danger "Ne committe jamais ces valeurs"
    Traite les trois tokens comme des mots de passe. S'ils fuitent (chat, screenshot, commit), [révoque-les immédiatement](https://eu.api.ovh.com/me/api/credential).

## 2. Découvrir ton billing account et ta ligne SIP

=== "Docker"

    ```bash
    docker run --rm \
      -e OVH_APPLICATION_KEY=... \
      -e OVH_APPLICATION_SECRET=... \
      -e OVH_CONSUMER_KEY=... \
      ghcr.io/raedkit/ovh-voip-spam-filter:latest discover
    ```

=== "PyPI"

    ```bash
    pip install ovh-voip-spam-filter
    export OVH_APPLICATION_KEY=...
    export OVH_APPLICATION_SECRET=...
    export OVH_CONSUMER_KEY=...
    ovh-voip-spam-filter discover
    ```

La sortie ressemble à :

```text
Found 1 billing account(s):

  billing_account = ab-12345-ovh
    service_name    = 0033xxxxxxxx
```

Note le `billing_account` et le `service_name` à protéger.

## 3. Dry-run

Prévisualise ce que le sync ferait sans appliquer :

```bash
docker run --rm \
  -e OVH_APPLICATION_KEY=... \
  -e OVH_APPLICATION_SECRET=... \
  -e OVH_CONSUMER_KEY=... \
  -e OVH_BILLING_ACCOUNT=ab-12345-ovh \
  -e OVH_SERVICE_NAME=0033xxxxxxxx \
  ghcr.io/raedkit/ovh-voip-spam-filter:latest sync --dry-run
```

Tu verras le plan de réconciliation et la durée estimée.

## 4. Sync réel

Enlève `--dry-run` :

```bash
docker run --rm \
  -e OVH_APPLICATION_KEY=... \
  -e OVH_APPLICATION_SECRET=... \
  -e OVH_CONSUMER_KEY=... \
  -e OVH_BILLING_ACCOUNT=ab-12345-ovh \
  -e OVH_SERVICE_NAME=0033xxxxxxxx \
  ghcr.io/raedkit/ovh-voip-spam-filter:latest sync
```

Le bootstrap prend environ **13 minutes** au throttle par défaut (1 req/s pour 643 entrées). Les runs suivants ne POSTent que les changements (quelques secondes en général).

## 5. Vérifier

Soit tu relances `sync` (doit être idempotent : 0 changement), soit tu te connectes au Manager OVH et tu vérifies la section "Filtrage des appels" de ta ligne SIP — la blocklist contient maintenant les préfixes.

Test fonctionnel : demande à quelqu'un d'appeler depuis un numéro commençant par un des préfixes bloqués (par exemple `+33 2 70 xx xx xx`). L'appel doit être rejeté.

## Étapes suivantes

- [Configuration](configuration.md) — toutes les variables d'env et flags CLI.
- [Sémantique de réconciliation](reconciliation.md) — strict normal vs additif dégradé.
- [Docker](docker.md) — détails de l'image et notes Kubernetes.
- [Feuille de route](roadmap.md) — ce qui est prévu et comment contribuer.

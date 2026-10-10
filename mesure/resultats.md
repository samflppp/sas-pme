# Mesure sur le corpus

Généré le 2026-10-10 par `python3 -m mesure.mesurer`, sur `demo/corpus/corpus.json` (généré le 2026-10-10T14:14:42Z).

| Contrôles | Détection (malveillantes arrêtées) | Fausses alertes (saines arrêtées) |
|---|---|---|
| Contrôles seuls (nom : typosquat) | 1 / 30 (3 %) | 0 / 50 (0 %) |

Une version est arrêtée si un contrôle lève un signal FORT ou BLOQUANT.

## Contrôles seuls (nom : typosquat)

**Arrêtées :**
- `prosocks` : « prosocks » imite le paquet populaire « pysocks »

**Malveillantes manquées (29) :** `agent-vx`, `pafer`, `webreader`, `media-manager5`, `ig-gox`, `anthropic-sdk`, `zencleaner`, `caoxiltts`, `infrabench`, `dedh-devops-automation`, `shortneer`, `spo365-graph`, `friendly-tools`, `friendly-greeting-tools`, `beautifytext`, `cleanup-string`, `bfox-build-utils`, `queeuees`, `aseitylab`, `scrapetools2`, `aseity`, `caracas4check`, `requests-cache-utils`, `sherpy`, `tego-managed-agents-test`, `reqparser`, `memoryos`, `auclean`, `snap-queue`

## Limites

- 26 des 30 paquets malveillants n'existaient plus sur PyPI le 2026-10-10. Sans télécharger leurs
  archives (interdit hors sandbox), seuls leur nom et leur version sont lus. Les contrôles sur le code
  (installation, `exec`/`base64`, domaines) et la sandbox se mesureront sur `demo/paquets/`.
- Les 50 versions saines sont des paquets populaires, donc dans la liste du contrôle de typosquat :
  leurs 0 % de fausses alertes sont acquis par construction. Il faudra des paquets sains peu connus.
- Le contrôle « présent dans OpenSSF malicious-packages » n'est pas compté : le corpus vient de cette
  même liste, il détecterait 100 % par construction.
- Le délai de 3 jours n'est pas compté ici : il faudrait la date de publication de chaque version
  malveillante sur PyPI, que le rapport OpenSSF ne donne pas toujours.

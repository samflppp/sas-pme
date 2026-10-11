# Point C — agent qui réessaie et IA pragmatique déployés (réponse à B) — 2026-10-11

## Réponses à B (`B-serveur-reessaie`, `B-ia-pragmatique`)
- **(Agent : recopier `agent_installation.py`, relancer le service)** **Fait.** J'ai relu ton
  changement dans `infra/serveur/` : ok. Seuls des noms déjà vérifiés sont relancés, l'attente
  s'arrête au bout de 30 min, et l'option « roues seulement » est gardée. Sur le serveur :
  `/opt/sas-agent/agent_installation.py` est identique au dépôt (md5 `d8872f62…`), et
  `agent-installation` est actif.
- **(Plateforme : `main`, puis relancer le web)** **Fait.** `main` (#123) est déployé. Web, faux PyPI
  et faux npm sont relancés par `~/h16.sh`. La base est gardée (celle de la vidéo, avec
  `admin` et `dev`). Suite locale : 773 verts.
- L'IP de l'admin alterne entre deux adresses : SSH est ouvert aux deux, et à rien d'autre.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| — | Aucune | — | — |

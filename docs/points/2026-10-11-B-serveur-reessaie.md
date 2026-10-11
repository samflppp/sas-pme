# Point B (Mouabd19) — le serveur installe tout seul, même pendant l'analyse — 2026-10-11

Constat de Mouabd19 en préparant la vidéo : la pipeline va au bout, mais le panneau Serveur reste
sur « en attente des requêtes du serveur ».

## Cause
L'agent du serveur (`infra/serveur/agent_installation.py`) lançait `pip install` **une seule
fois**, dès la demande. À ce moment-là, la version n'est pas encore analysée ni publiée : pip ne
trouve rien et l'agent abandonnait. Il fallait relancer pip à la main.

## Fait
**J'ai touché aux dossiers de C** (`infra/serveur/`) **et de A** (`plateforme/web/direct.py`,
gabarit, `direct.js`). C'est dit ici (règle 2).
- **Agent** : un pip qui échoue est retenu (`/var/lib/sas-agent/attente.json`), puis relancé
  toutes les 20 s (`SAS_AGENT_REESSAI`) jusqu'à ce qu'il réussisse, pendant 30 min au plus
  (`SAS_AGENT_PATIENCE`).
  - Une version bloquée n'arrive jamais : au bout du délai, l'agent abandonne.
  - Seul un nom déjà vérifié (signature, âge, nonce) est relancé, jamais une nouvelle demande.
  - L'attente survit à un redémarrage.
- **Panneau** : pendant l'analyse, il affiche « pas encore servie : le serveur réessaie dès que
  la version est publiée… », puis « ✓ installée ». Le « ✗ aucune version servie » (règle de A)
  reste pour une version qui n'arrivera pas seule : bloquée ou à revoir.

## Vérifié
- 3 tests neufs pour l'agent (relance, redémarrage et abandon, code de retour de pip), 1 pour le
  panneau. Un test de A est adapté : une version encore en attente a maintenant une installation
  à venir. Code cassé une fois : les tests sont passés au rouge.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Sur le serveur : recopier `agent_installation.py` dans `/opt/sas-agent/`, puis `sudo systemctl restart agent-installation` (même procédure que `installer.sh`, étape 11 bis) ; sur la plateforme : `git pull`, puis relancer le web | vidéo | fait |
| A (Sam) | Relire le message « réessaie » du panneau | rien | ok |

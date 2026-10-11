# Point B (Mouabd19) — une IA plus pragmatique — 2026-10-11

Constat de Mouabd19 sur le site : l'IA est trop dure. Sur un paquet propre (rien en statique, rien
en sandbox), elle écrivait « code_inject (moyen), fichiers_sensibles (moyen) » et une explication
alarmante. Il veut qu'elle liste les failles possibles, mais qu'elle parte du principe que tout
n'est pas malveillant.

## Fait (`plateforme/pipeline/llm.py`, mon dossier)
- **Prompt** :
  - « la plupart des paquets sont sains » ;
  - un appel réseau, une lecture de fichier ou un import dynamique sont normaux s'ils collent au
    rôle du paquet ;
  - pas d'alerte pour un simple lien ;
  - « fort » seulement sur une preuve concrète, « info » pour les points d'attention ;
  - l'explication commence par un avis d'ensemble (« Rien d'inquiétant », « Un point à
    vérifier », « Comportement malveillant »), puis liste les points d'attention.
- **Code** : quand ni la sandbox ni l'analyse statique n'ont relevé au moins un « moyen », chaque
  signal du LLM descend à **info** (marqué `sans_constat`). Avant, seul un « fort » descendait, à
  « moyen ». Le LLM n'abaisse ainsi que ses propres alertes : un constat du code, lui, ne bouge
  jamais. La règle « le code décide » tient.
- **Rien ne change dans les verdicts** : le LLM ne mettait déjà rien « à revoir » sans constat. La
  détection de la mesure est donc inchangée. Les fausses alertes ne peuvent que baisser.

## Vérifié
- 3 tests neufs et 4 adaptés (`test_llm.py`) : l'ancrage reste testé avec un constat présent.
  Règle retirée une fois : les tests sont passés au rouge. Suite complète verte.
- **Pas vérifié avec le vrai Ollama** (absent de mon conteneur) : le ton de l'explication se voit
  sur le site après le redéploiement.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | `git pull` sur la plateforme, puis relancer le web (`~/h16.sh`) | vidéo | fait |

# Point C — base neuve prête pour la vidéo (réponse à B) — 2026-10-11

## Réponses à B (`B-demande-c-prise-video`, `B-demande-c-base-neuve`)
- **(Base neuve, paquets par numéro de prise)** **Prêt.** À 07:13 UTC, sur la plateforme :
  - `main` (#119) est déployé ;
  - l'ancienne base est archivée dans `~/bases-archivees/sas-h16.db.20261011-071327` (la base du
    site est `~/sas-h16.db`, fixée par `~/h16.sh`) ;
  - le web, le faux PyPI (8081) et le faux npm (8082) sont relancés ; les deux fausses sources
    servent `demo-piege-2` et `demo-npm-piege-2` ;
  - la base neuve est vide (0 version). Comptes : `admin` et `dev`, recréé avec son mot de passe
    habituel.
- Accès rétabli au passage : l'IP de l'admin avait changé et les identifiants AWS du workshop
  avaient expiré. SSH est rouvert pour la nouvelle IP seulement. La démo n'a pas été touchée.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| — | Aucune : la vidéo peut commencer (prise « vidéo » = paquets `-2`) | — | — |

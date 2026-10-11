# Point B (Mouabd19) — page Direct : une demande npm — 2026-10-11

Constat de Mouabd19, sur la démo AWS : on demande `requests` dans npm, et deux erreurs
apparaissent sur la page Direct.

## 1. Sandbox : « NotImplementedError: sandbox v1 : pip seulement » → déjà réglé par C
Ce message n'existe plus dans `main`. C a mis la plateforme AWS à jour entre-temps
(`2026-10-11-C-npm-wireguard-aws.md` : `ms` va jusqu'à « publiée »). `requests` 0.3.0 avait été
analysé à 03:21, **avant** cette mise à jour. La demande de 03:26 a retrouvé cette version déjà
connue, avec son ancienne analyse. Elle reste « à revoir » : un humain l'approuve ou la bloque.
La redemander ne la ré-analyse pas.

## 2. Panneau Serveur : « pip install requests » puis « ✗ M0 : pip seulement » → corrigé
**J'ai touché au dossier de A** (`plateforme/web/`), c'est dit ici (règle 2).
- L'agent d'installation du serveur de démo n'installe que pip. Une demande npm partait quand
  même vers lui. La passerelle la refusait, et le panneau affichait une commande pip fausse et
  une erreur.
- Désormais :
  - une demande npm **n'est plus envoyée** à l'agent ;
  - le panneau montre `npm install <nom>`, le registre de la passerelle
    (`SAS_REGISTRE_SERVEUR`, défaut `http://10.42.2.10:4873/`), « pas de repli vers
    registry.npmjs.org », et que la commande se tape à la main sur le serveur ;
  - rien d'autre n'est affiché ni inventé pour npm.
- Pour pip, rien ne change.
- L'étape de téléchargement s'appelle maintenant « Téléchargement depuis le registre public
  (PyPI ou npm) ».

## Vérifié
- Nouveau test `test_une_demande_npm_ne_lance_pas_pip_sur_le_serveur`. Je l'ai vu rouge, puis
  rouge à nouveau quand j'ai retiré le correctif.
- Suite complète : 719 verts, 18 sautés (Docker arrêté dans mon conteneur).

## Note sur le paquet `requests` dans npm
`requests` est un paquet Python. Sur npm, un vieux paquet porte ce nom (0.3.0, publié en 2019).
Pour une démo npm, demander plutôt `ms`, `is-number`, `chalk` ou `axios`.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Après la fusion, mettre à jour le code web de la plateforme AWS (panneau Serveur npm) | démo npm | fait |
| A (Sam) | Relire le changement du panneau Serveur (`direct.py`, `direct.html`, `direct.js`, `app.py`) | rien | ok / remarques |

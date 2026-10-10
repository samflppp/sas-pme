# Point B (Mouabd19) — dépendances dans le pipeline — 2026-10-10

## Fait
- **`demander(eco, nom)` enregistre aussi toutes les dépendances**, transitives comprises, chacune
  `en_attente` : chacune suivra le même parcours (délai de 3 jours, analyse, verdict, signature)
  qu'un paquet demandé. Rien n'arrive sur les serveurs sans être vérifié.
- Seules les dépendances obligatoires sur les serveurs sont prises : ni les extras
  (`extra == "socks"`), ni celles d'une autre plateforme ou d'un autre Python. La cible est figée
  dans `pypi.CIBLE` (CPython 3.12, Linux x86_64).
- Pour chaque dépendance, on prend la dernière version mûre **qui respecte la contrainte**
  (`urllib3<3` donne la dernière 2.x). Les cycles sont gérés. Tout est résolu avant d'écrire : si une
  dépendance manque, rien n'est enregistré (`LookupError` qui la nomme). Au-delà de 100 paquets,
  la demande est refusée.
- Essai réel : `requests` donne `requests`, `urllib3`, `idna`, `certifi`, `charset-normalizer`.

## Disponible pour vous
- Rien de nouveau à appeler : même `demander(eco, nom)`, et `traiter()` publie chaque paquet
  séparément. Quand toutes les dépendances sont publiées, `pip install requests` marche sur le
  serveur **sans `--no-deps`**.

## Réponses à vos demandes
- **(C, « dépendances ou `--no-deps` »)** Les dépendances passent par le pipeline (décision de B).
  Pour H3, `--no-deps` reste un repli tant que tout n'est pas publié.

## Limites connues
- Si deux paquets demandent deux plages incompatibles d'une même dépendance, la première trouvée
  l'emporte.
- `telecharger()` prend tous les fichiers d'une version : pour un paquet compilé (`pydantic-core`),
  ce sont des dizaines de roues. Filtrer sur `pypi.CIBLE` en M1.

## Ensuite
- M1 : délai réglable en démo, veille OSV, autres contrôles statiques, politique déterministe, LLM.

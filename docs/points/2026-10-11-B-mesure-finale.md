# Point B (Mouabd19) — M3 : mesure finale, lignes 1 et 2 ; ligne 3 à lancer sur AWS — 2026-10-11

## Fait
- **La mesure en trois lignes** (`mesure/mesurer.py`, `mesure/sandbox.py`). Chaque ligne ajoute une
  couche du pipeline à la précédente, sur le même corpus (`demo/corpus/corpus_code.json`) :
  128 versions malveillantes (Datadog) et 98 saines (PyPI, dont 48 peu connues).
- **Résultats** (`mesure/resultats.md`, le 2026-10-11) :

| Ligne | Détection (malveillantes arrêtées) | Fausses alertes (saines arrêtées) |
|---|---|---|
| 1. Contrôles seuls (nom + code) | 93 / 128 (73 %) | 0 / 98 (0 %) |
| 2. + sandbox | **103 / 128 (80 %)** | **0 / 98 (0 %)** |
| 3. + LLM/RAG | à lancer sur AWS (ci-dessous) | — |

- **Ce que la sandbox ajoute (10 versions), toutes sur un comportement observé :**
  - requêtes DNS vers l'attaquant (`bytedance-chat` → `0wn.sh`) ;
  - sondage du cloud et de Kubernetes (`b10connoisseur` : `169.254.169.254`, `kubernetes.default`,
    `/proc/…/environ`) ;
  - commandes lancées (`powershell … CBLines.exe`, `ifconfig`, `start python /tmp/…`) ;
  - lecture de `/etc/passwd` (`lightning` 2.6.3, `0wneg`).
- **Comment c'est mesuré :**
  - chaque version passe par la vraie sandbox de C : 60 s de battement, leurres, `strace`, réseau
    interne, 4 analyses à la fois ;
  - les échantillons sont remis en sdist ou en roue à partir de leurs fichiers, sans rien
    exécuter hors de la sandbox ;
  - les 226 rapports sont gardés dans `mesure/rapports_sandbox/` : la mesure se rejoue sans
    relancer la sandbox.
- **Ligne 3 : le LLM n'est interrogé que là où il peut changer le résultat**, c'est-à-dire sur une
  version pas encore arrêtée qui a un constat MOYEN hors du LLM.
  - Partout ailleurs, il ne peut rien changer : il n'abaisse jamais un risque, et sans ce constat
    son FORT redescend (#76).
  - Ici, cela fait **5 versions sur 226** (4 malveillantes, 1 saine).
- 8 tests neufs, vus rouges avant le code, et 6 mutations vues rouges. Les tests couvrent :
  - le réemballage : sdist, roue dépliée avec son RECORD réécrit, roue minimale, archive
    d'origine ;
  - le cache des rapports ;
  - l'analyse impossible, comptée comme dans le pipeline ;
  - le LLM interrogé seulement là où il compte ;
  - l'ordre des lignes.

## Ce que disent les chiffres, honnêtement (pour le deck et la fiche de défense)
- **La sandbox paie :** +10 détections (73 % → 80 %) sans aucune fausse alerte. Elle voit ce que
  le code cache : un DNS, une commande, un fichier lu.
- **Une règle simple fait presque tout le travail de détection** : c'est la réponse au premortem.
  Le LLM ne peut changer le verdict que sur 5 versions sur 226. Sa valeur est ailleurs :
  - il **explique** en français, avec des références (CWE, ATT&CK, cas connus) ;
  - il **aggrave** un doute réel.

  Ce n'est pas une faiblesse à cacher : c'est le choix « le code décide, l'IA explique », et il se
  mesure.
- **Limite principale :** la sandbox installe sans les dépendances, comme le produit. Elle n'a donc
  pu observer l'import que de 58 des 98 saines. 12 des 25 malveillantes manquées ont échoué à
  l'import, dont ultralytics 8.3.41, 8.3.42 et 8.3.46, dont la charge part justement à l'import.
- **Une idée hors périmètre (règle 7), notée, pas codée :** installer dans la sandbox les
  dépendances depuis le dépôt des versions déjà approuvées. Cela verrait ultralytics. C'est pour la
  diapositive « what's next ».
- Autres limites : `mesure/resultats.md` § Limites (campagnes en série, groupe « populaires »
  optimiste, cibles Windows, image construite hors AWS avec le `strace` de l'hôte).

## Réponses à A (Sam), `A-m2-clos`
- **(Relire `docs/defense.md` § 3 et § 4)** Relu. Mes propositions :
  - **§ 3** : remplacer le tableau par celui de ce point, lignes 1 et 2, puis la ligne 3 dès que C
    l'a. Remplacer aussi la phrase « ils manquent 35 versions, dont ultralytics… : c'est le rôle du
    délai et de la sandbox » par : « la sandbox en arrête 10 de plus, sans fausse alerte ; elle
    manque ultralytics, qui ne s'importe pas sans ses dépendances : c'est le rôle du délai et de la
    veille ». Ajouter la phrase sur le LLM : « il ne peut changer le verdict que sur 5 versions sur
    226 : il explique, le code décide ».
  - **§ 4, « Une IA qui lit du code se trompe »** : la règle a changé depuis ta relecture (#76).
    Un FORT du LLM doit s'appuyer sur ce que le paquet a montré, **et** sur un constat statique ou
    de sandbox d'au moins MOYEN. Elle vient de trois fausses alertes vues en répétition : certifi,
    idna, puis requests.
  - **§ 4, « Un paquet peut détecter la sandbox »** : ajouter « et une version qui ne s'importe pas
    sans ses dépendances n'est observée qu'à l'installation (ultralytics) ».
  - Le reste du § 4 est juste pour ma partie.
- **(Quand la mesure finale est sur `main`)** Les lignes 1 et 2 y sont avec cette PR. Je te
  préviens par un point quand C aura la ligne 3.

## Demande à C (STEUSSO) : la ligne 3 sur la plateforme (environ 15 min, dont 5 de LLM)
Depuis `~/sas-pme`, après `git pull` :

```sh
export SAS_CLE_JOURNAL=$(cat ~/.sas-cle-journal)
D=~/mesure && mkdir -p $D/cache/rapports && cp mesure/rapports_sandbox/*.json $D/cache/rapports/
git clone --depth 1 --filter=blob:none --no-checkout \
    https://github.com/DataDog/malicious-software-packages-dataset $D/dd
.venv/bin/python -I -c "import json; print('\n'.join(e['echantillon'] for e in json.load(open('demo/corpus/corpus_code.json'))['malveillants']))" \
    | xargs git -C $D/dd checkout HEAD --
.venv/bin/python -I mesure/mesurer.py --echantillons $D/dd --cache $D/cache --llm
```

- **Les échantillons ne sont pas exécutés par cette commande :**
  - la ligne 1 les lit seulement ;
  - la ligne 2 reprend les rapports de sandbox copiés dans le cache ;
  - la ligne 3 n'envoie au LLM que des constats et des rapports.
- Les archives saines se téléchargent depuis PyPI (environ 1 Go).
- **Attendu :** le tableau à trois lignes, et la note « LLM interrogé sur 5 versions ».
- **Ensuite :** commite `mesure/resultats.md` dans ta PR, ou colle le tableau dans ton point, et je
  le reporte.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Le bloc ci-dessus : la ligne 3 | H22 (mesure) | le tableau |
| A (Sam) | Reporter les chiffres et les trois corrections ci-dessus dans `docs/defense.md` | H22 | ok |

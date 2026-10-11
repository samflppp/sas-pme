# Point B (Mouabd19) — trio vert / orange / rouge pour l'enregistrement vidéo — 2026-10-11

## Le problème
Pour la vidéo, on veut, pour PyPI et pour npm, un paquet **approuvé** (vert), un **à revoir**
(orange) et un **bloqué** (rouge). On ne les avait pas, pour deux raisons :
1. **De vrais paquets ne sont jamais bloqués**, et c'est voulu : seule une preuve d'attaque bloque
   (leurre lu, exfiltration, avis OSV, retrait du registre). Les vraies versions piégées sont
   retirées avant nos 3 jours.
2. **Les sources de démo n'étaient pas prêtes :**
   - côté PyPI, le faux PyPI ne sortait que `demo-horodatage` 1.0 ; il fallait publier 1.1, 1.2 et
     1.3 une par une, puis attendre le délai ;
   - côté npm, **il n'y avait aucune source de démo sur AWS**. Mon essai local `demo-npm-piege`
     n'existait que dans mon conteneur.

## Fait (`demo/paquets/`, mon dossier)
Six paquets, publiés « il y a 400 jours », donc **mûrs tout de suite** : rien à attendre ni à
publier à la main.

| Écosystème | Vert (approuvé) | Orange (à revoir) | Rouge (bloqué) |
|---|---|---|---|
| pypi | `demo-sain` | `demo-a-revoir` | `demo-piege` |
| npm | `demo-npm-sain` | `demo-npm-a-revoir` | `demo-npm-piege` |

- **Vert** : du code simple, aucun signal.
- **Orange** : une fonction qui enverrait un rapport vers un tunnel ngrok, jamais appelée. Elle
  lève un seul signal FORT (`domaine_suspect`), rien de bloquant : c'est à un humain de trancher.
- **Rouge** : le paquet PyPI lit `~/.aws/credentials` à l'import ; le paquet npm lit `~/.npmrc`
  dans son `postinstall`. Les deux appellent `collecte.attaquant-demo.invalid`, un domaine qui ne
  se résout jamais.
  - Signal BLOQUANT en statique (`exfiltration`).
  - En sandbox : `lit_leurre` (BLOQUANT), plus la requête DNS et la connexion vers l'attaquant.
- `faux_pypi.py` sert le trio PyPI en plus de `demo-horodatage`, inchangé.
- `faux_npm.py` (neuf, port 8082) sert le trio npm et relaie tout autre nom vers
  registry.npmjs.org.

## Vérifié
- Tests `tests/demo/test_trio_demo.py` : les 6 verdicts viennent de la vraie analyse statique et
  de la vraie politique. J'ai cassé le paquet npm piégé une fois : son test tombe au rouge.
- **Vraie sandbox Docker** sur les 6 :
  - sains et à revoir : aucun DNS, aucun leurre, aucun signal ;
  - `demo-piege` : leurre `~/.aws/credentials` lu, DNS `collecte.attaquant-demo.invalid` ;
  - `demo-npm-piege` : leurre `~/.npmrc` lu, même DNS, `node post.js` lancé.
- Suite complète : 733 verts.

## Demande à C (STEUSSO), sur la plateforme, avant d'enregistrer
```bash
cd ~/sas-pme && git pull origin main
# le faux PyPI, relancé pour qu'il connaisse le trio (port 8081)
pkill -f demo/paquets/faux_pypi.py; .venv/bin/python demo/paquets/faux_pypi.py > ~/faux_pypi.log 2>&1 &
# le faux npm (neuf, port 8082)
.venv/bin/python demo/paquets/faux_npm.py > ~/faux_npm.log 2>&1 &
curl -s localhost:8081/pypi/demo-piege/json | head -c 120; echo
curl -s localhost:8082/demo-npm-piege | head -c 120; echo
```
Puis relancer le web avec, **en plus** des variables habituelles :
```bash
export SAS_PYPI_URL=http://127.0.0.1:8081 SAS_NPM_URL=http://127.0.0.1:8082
```
`SAS_NPM_URL` est lu au démarrage : il faut relancer `uvicorn`.

## Pour l'enregistrement
Dans « Demandes », demander les six noms du tableau, un par un. Chacun va de l'analyse à son
verdict en quelques minutes (sandbox et LLM sur CPU), sans délai d'attente.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (STEUSSO) | Les commandes ci-dessus, puis dire si les 6 paquets finissent dans la bonne couleur | vidéo | oui / capture |
| A (Sam) | Ajouter le trio à `demo/script.md` si tu veux le garder dans le déroulé | vidéo | ok |

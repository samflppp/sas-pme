# Point B (Mouabd19) — RAG essayé à pleine échelle, passages corrigés (M2) — 2026-10-10

## Fait
- **Essai du RAG sur le vrai export OSV** (36 Mo, 10/10), avec le vrai Chroma. Seul le plongement
  de nomic est remplacé, par un sac de mots haché, car Ollama est injoignable d'ici.
  - L'index se construit sans erreur : **16 473 documents en 26 s**, 110 Mo sur disque. Avec
    nomic sur le GPU, compter quelques minutes de plus.
  - L'essai a montré trois défauts, corrigés ici :
    1. **2 100 avis OpenSSF ne disent rien** : seulement « Malicious code in X », sans détails ni
       CWE. Ils ne sont plus indexés, car ils prenaient des places au LLM sans rien lui
       apprendre.
    2. **Un même texte de campagne se répète** sur des milliers d'avis (EsqueleSquad : 5 423).
       Chaque texte n'occupe plus qu'un passage sur les 5.
    3. **Les fiches CWE, CAPEC et ATT&CK n'apparaissaient jamais**, noyées dans 16 000 avis. Sur
       les 5 passages, 2 leur sont maintenant réservés : 3 cas connus, plus 2 fiches.
  - **Résultat pour la démo 1.2** (DNS vers l'attaquant, `~/.aws/credentials` lu) : 3 paquets
    malveillants connus qui volent des identifiants, plus **T1552.001** (identifiants dans des
    fichiers) et **CWE-522** (identifiants mal protégés).
- 3 nouveaux tests, chacun cassé une fois ; 385 passent.

## Disponible pour vous
- Rien ne change pour vous. `rag.passages` rend toujours au plus 5 passages `(ref, texte)`.

## Demandes
Les demandes des points `B-rag` et `B-veille-rss` restent ouvertes. Les voici en un seul bloc, à
lancer sur la plateforme AWS. C'est tout ce qui manque pour clore le M2 de B.

| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| C (ou la personne qui reprend son travail) | Le bloc ci-dessous, puis coller sa sortie dans ton point | H16 | la sortie |

À lancer **depuis la racine du dépôt**, comme `uvicorn` dans `demo/script.md`. L'index va alors
dans `rag_index/`, là où le pipeline le cherche, sans rien régler. Ça corrige mon point `B-rag`,
qui disait à tort de lancer depuis le dossier du pipeline.

```sh
git pull && .venv/bin/pip install -e .          # chromadb
ollama pull nomic-embed-text
.venv/bin/python -I -m plateforme.pipeline.rag.construire   # quelques minutes
.venv/bin/python -m mesure.llm_demo --rag
.venv/bin/python -I -c "import httpx; from plateforme.pipeline import veille_rss as v; [print(u, httpx.get(u, follow_redirects=True, timeout=20).status_code) for u in v.flux()]"
```

**Ce que j'attends :**
- la construction affiche « N documents indexés », avec N autour de 16 500 ;
- pour 1.2, `llm_demo` affiche une ligne `cite : …` avec au moins une référence ;
- chaque flux RSS affiche un code HTTP. Si un flux ne répond pas 200, je le retire de la liste.

## Ensuite
- Selon la sortie sur AWS, ajuster la liste des flux. Puis le point H16 et le M3.

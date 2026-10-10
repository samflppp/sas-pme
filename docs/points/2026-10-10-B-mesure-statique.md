# Point B (Mouabd19) — mesure v1 : contrôles statiques seuls — 2026-10-10

C'est la tâche « en attendant » du M1 (`docs/roadmap.md`). Résultats complets :
`mesure/resultats.md`.

## Fait
- **Résultat.** Une version est « arrêtée » si un contrôle lève un signal FORT ou BLOQUANT : elle
  passe alors « à revoir » ou « bloquée », et n'atteint pas les serveurs.

  | Contrôles | Détection | Fausses alertes |
  |---|---|---|
  | Nom seul (typosquat), corpus OpenSSF | 1 / 30 (3 %) | 0 / 50 (0 %) |
  | **Contrôles statiques (nom + code)** | **93 / 128 (73 %)** | **0 / 98 (0 %)** |

  - **Détection, par catégorie :**
    - bibliothèques connues compromises : 16 sur 28 (dont ultralytics 8.3.45, litellm 1.82.8,
      mistralai, telnyx, xinference) ;
    - paquets malveillants dès le départ : 77 sur 100.
  - **Fausses alertes :** 0 sur 50 mises à jour populaires, et 0 sur 48 paquets peu connus. Ce
    second groupe n'a servi à aucun réglage : c'est le chiffre honnête.
- **Les malveillants :** 128 échantillons réels du jeu de Datadog
  (`DataDog/malicious-software-packages-dataset`). Il garde le code de paquets retirés de PyPI
  depuis, ce qui contourne la limite du corpus OpenSSF (26 paquets sur 30 introuvables).
  - Ce sont les 28 bibliothèques compromises, plus 100 paquets « malveillants dès le départ »
    pris à intervalle régulier.
  - Ils sont **lus seulement** : zips chiffrés au mot de passe public, déchiffrés en mémoire,
    Python en `-I`, dossier à part. Rien n'est installé ni exécuté.
- **Les sains :** vraies archives de PyPI, filtrées pour la cible comme dans le pipeline. Chaque
  version est comparée à sa version précédente, comme le pipeline le fait pour une mise à jour.
- **Le code :**
  - `mesure/statique.py` : lecture des échantillons. Il retrouve la racine du paquet, ramène les
    chemins doublés du jeu de données, garde les deux copies roue et sources, et ouvre un zip
    imbriqué ;
  - `demo/corpus/construire_code.py` : construit `demo/corpus/corpus_code.json` ;
  - `mesure/mesurer.py` : seconde ligne du tableau. Une version illisible est retirée du compte
    et listée, au lieu de compter comme « non arrêtée ».
- 16 nouveaux tests, chacun cassé une fois. 342 tests passent.

## Ce que la mesure apprend (pour le deck)
- **Une règle simple ne suffit pas, mais des règles sur le code font beaucoup.**
  - Le nom seul arrête 3 %. Le nom et le code arrêtent 73 %, sans fausse alerte sur 98 paquets
    sains.
  - Les détections sont des cas réels : reverse shells dans `setup.py`, exfiltration vers
    `webhook.site` ou un webhook Discord, PowerShell encodé, `exec(base64…)` à l'installation.
- **Ce que le statique rate, et pourquoi il faut la sandbox et le LLM :**
  - Les grosses bibliothèques compromises (ultralytics 8.3.41/42/46, lightning, durabletask,
    num2words, guardrails-ai) cachent la charge dans un module ordinaire, loin de `setup.py`. Elle
    télécharge depuis des domaines banals (`github.com`) ou passe par du code applicatif.
  - Des paquets lancent un `.exe` téléchargé depuis leur `__init__.py` (`websend`) : aucune règle
    ne vise « réseau + processus à l'import ».
  - C'est exactement ce que la sandbox voit (DNS, connexion, processus) et ce que le LLM peut
    signaler. Ce sont les colonnes « + sandbox » et « + LLM/RAG » de la mesure finale (M3).
- **Idée notée, pas codée** (règle 7, et pour ne pas régler les règles sur l'échantillon mesuré) :
  rendre FORT un `subprocess` ou un téléchargement exécuté dans un `__init__.py` de premier
  niveau.

## Limites (aussi dans `resultats.md`)
- Les échantillons de Datadog (2022 à 2026) contiennent des campagnes en série (même code sous
  plusieurs noms) : la détection compte chaque version.
- Les bibliothèques compromises sont analysées en entier, sans leur version saine précédente. Le
  pipeline, lui, ne regarderait que ce qui change, ce qui est sans doute un peu plus favorable.
- Les 50 sains populaires recoupent les 20 paquets qui ont servi à régler les règles : ce groupe
  est optimiste. Les 48 peu connus ne le sont pas.
- **Ne sont pas comptés :**
  - les métadonnées (MOYEN au plus) ;
  - la veille OSV (100 % par construction) ;
  - le délai de 3 jours.

## Refaire la mesure
```
git clone --depth 1 --filter=blob:none --no-checkout \
    https://github.com/DataDog/malicious-software-packages-dataset <dossier>/dd
# puis les deux commandes en tête de mesure/mesurer.py (≈ 400 Mo d'échantillons, ≈ 1 Go d'archives
# saines, 10 min)
```

## Réponses à vos demandes
- **(C, C-h10-aws : `fichier_sensibles` du 3B, le schéma l'accepte-t-il ?)** Oui, c'est voulu. La
  sorte d'un signal du LLM est une étiquette libre en `snake_case` (40 caractères au plus) : on ne
  peut pas lister d'avance ce qu'il remarque. Ce qui est fermé, c'est son **niveau**, au plus
  FORT : jamais BLOQUANT, jamais une approbation.
  - Le vrai problème du 3B n'est pas le nom, c'est le FORT inventé sur la 1.1 saine : elle passe
    « à revoir », donc un humain tranche, mais c'est une fausse alerte à l'écran pendant la démo.
  - **D'accord pour garder le 7B** : c'est déjà le défaut (#33), et ta mesure le confirme
    (conforme, juste sur 1.1 et 1.2, 47 s pour 1.2).

## Demandes
Aucune.

## Ensuite
- M3 : colonnes « + sandbox » (la v1 de C sur ces échantillons, dans la sandbox seulement) et
  « + LLM/RAG ».
- M2 : RAG.

# Fiche de défense — Pipelad (1 page)

Version longue, avec les preuves et les sources : [`defense.md`](defense.md).

**Scénario de menace.** Une version piégée d'un paquet pip ou npm (mainteneur compromis,
typosquat, cas réels : ultralytics 8.3.41-8.3.46 en décembre 2024, ver Shai-Hulud sur npm en
septembre 2025) s'installe sur les serveurs d'une PME sans équipe sécurité. Elle vole des secrets
(`~/.aws/credentials`, jetons) et les exfiltre. **Pipelad** : une plateforme agréée, seule reliée à
Internet, attend 3 jours chaque nouvelle version, l'analyse sur place (statique, sandbox, IA locale
+ RAG), puis la signe pour une passerelle **sans Internet** où les serveurs s'approvisionnent.

**Fonctions NIST CSF 2.0 couvertes**

| Fonction | Ce que fait Pipelad |
|---|---|
| **Detect** | analyse statique, sandbox sans réseau avec leurres (DNS, connexions, fichiers lus), veille OSV et flux de chercheurs, LLM local qui explique |
| **Respond** | version bloquée ou « à revoir » (décision humaine) ; révocation en un geste, retirée de la passerelle ; l'inventaire dit quels serveurs l'ont |
| **Protect** | délai de 3 jours imposé par le réseau ; serveurs sans route vers Internet ; publication signée Ed25519 + TLS mutuel |
| **Identify** | inventaire de ce que les serveurs ont réellement installé |
| **Govern** | journal en ajout seul, chaîné par HMAC ; « le code décide, l'IA explique » |
| **Recover** | sauvegardes `restic` chiffrées, restauration testée (journal intact) |

**Techniques et risques traités**
- **MITRE ATT&CK :** T1195.001 (compromission de dépendances logicielles) ; T1552.001
  (identifiants dans des fichiers : leurres lus en sandbox) ; T1048 et T1071.004 (exfiltration,
  DNS : vus par le faux DNS) ; T1059.006 (code Python exécuté à l'installation ou à l'import).
- **OWASP Top 10 for LLM, LLM01 (injection de prompt) :** le code du paquet est donné au LLM comme
  donnée ; sa sortie est validée par un schéma ; il ne peut ni approuver ni bloquer, et un signal
  FORT sans preuve tirée du paquet redescend.

**Métriques obtenues** (mesure du 2026-10-11, `mesure/resultats.md`, 128 versions malveillantes
Datadog, 98 saines)

| | Détection | Fausses alertes |
|---|---|---|
| Contrôles seuls | 93 / 128 (73 %) | 0 / 98 |
| + sandbox | **103 / 128 (80 %)** | **0 / 98** |
| + LLM/RAG | 103 / 128 (80 %) | 0 / 98 |

- **Temps de détection :** environ 70 s d'analyse par version sur CPU, après le délai
  (répétition AWS : la version piégée de démo est bloquée 72 s après la fin de son délai).
- **Temps de réponse :** une version bloquée n'atteint jamais un serveur (exposition nulle) ; une
  révocation tardive se fait en un geste et retire immédiatement la version de la passerelle.
- **Robustesse vérifiée sur AWS :** publication forgée refusée (401) ; attaquant root sur la
  plateforme : 8 contrôles sur 8 (ni SSH vers les serveurs, ni Internet pour eux).

**Limites connues**
- La sandbox installe sans les dépendances : ultralytics, dont la charge part à l'import, lui
  échappe (c'est le rôle du délai et de la veille).
- Une plateforme réellement compromise peut signer une version piégée (suite : clé matérielle et
  double signature).
- Effacer les dernières entrées du journal n'est pas détecté (suite : ancre sur la passerelle).
- Pas de voie d'urgence par version, pas de SBOM ; pip et npm seulement ; mesure sur corpus, pas en
  production.

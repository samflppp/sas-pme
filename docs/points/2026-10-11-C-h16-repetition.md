# Point C — répétition à blanc H16 et matière M3 — 2026-10-11

## Fait
- **Plateforme prête pour H16** :
  - `main` redéployé dans `~/sas-pme` ;
  - index RAG : `…/sas-pme/rag_index 16473 documents` (commande de B) ;
  - image de la sandbox à jour ;
  - web relancé sur une **base neuve** `~/sas-h16.db` (lancement : `~/h16.sh`), faux PyPI sur 8081 ;
  - mot de passe `admin` dans `~/.sas-admin-mdp` sur la plateforme ;
  - tunnel : `ssh -F infra/secrets/ssh_config -N -L 8000:127.0.0.1:8000 sas-plateforme`.
- **Répétition à blanc complète**, avec `SAS_DELAI=120`, `SAS_SANDBOX_ATTENTE=10` et le 7B sur CPU :

| Étape | Résultat | Temps |
|---|---|---|
| Préparation : `demo-horodatage` 1.0 | publiée | 98 s |
| Préparation : `requests` et ses 4 dépendances | 3 publiées ; **certifi et idna « à revoir »** (voir plus bas) | 330 s |
| 1. serveur : `curl pypi.org` / `pip install requests` | échoue / marche | — |
| 2. 1.1 sortie → publiée ; `pip install -U` → 1.1 | ok, aucun signal FORT | 140 s (120 s de délai) |
| 3. 1.2 sortie 30 s après → **bloquée** | preuves statiques et sandbox (DNS de l'attaquant, leurre lu) ; `refs_rag` : CWE-522, T1552.005 | 72 s après la fin de son délai |
| 3 bis. serveur : `pip install demo-horodatage==1.2` | introuvable | — |
| 4. `demo/forger.sh` | `passerelle 401 : signature invalide` | 2 s |
| Relais depuis le serveur | `api.github.com` 200 ; `pypi.org` refusé | — |
| Révocation de 1.1 depuis l'interface | 200, `revoquee` ; le serveur ne peut plus la télécharger | immédiat |
| `/inventaire` | 1.1 en alerte (5 alertes au total) | — |
| Journal | `(True, None)`, 42 entrées | — |

  Les étapes 2 et 3 ensemble prennent **252 s** depuis la sortie de 1.1. Pour tenir 3 minutes, il
  faut lancer 1.1 et 1.2 avant la prise de parole, ou les couper au montage de la vidéo.
- **`demo/reseau.md`** : schéma réseau pour le deck ; barrières et preuve de chacune ;
  diapositive « et si la plateforme est compromise ? », écrite honnêtement ; découpage de la vidéo
  de 3 min.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| B | **Fausses alertes du LLM** : certifi 2026.7.22 et idna 3.20 passent « à revoir » sur un seul signal `llm fort`, sans rien en statique ni en sandbox. Pour certifi, la « preuve » est un passage du RAG recopié (« PTH file… payload stored in chunks in DNS records ») ; pour idna, « non reconnu dans la base de sécurité ». Elles pèseront dans la mesure (fausses alertes) | H16, mesure | correctif / avis |
| A | Pendant H16, approuver certifi et idna à la main : ça montre la décision humaine | H16 | ok |
| A | Reprendre le schéma et la diapositive « plateforme compromise » de `demo/reseau.md` dans le deck | M3 | ok / retouches |

## Ensuite
- M3 : enregistrer la vidéo pendant ou après H16 (découpage dans `demo/reseau.md` § 4).

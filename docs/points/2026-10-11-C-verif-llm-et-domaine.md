# Point C — vérification AWS du LLM (pour B) ; démo sur pipelad.tech — 2026-10-11

## Réponses à B (`B-verif-llm-aws`)
**Fait, et tout est conforme.** `main` (PR #75) est redéployé sur la plateforme. J'ai lancé ton
bloc, avec en plus `requests==2.34.2` :

| Ligne | Sortie |
|---|---|
| certifi 2026.7.22 | verdict **approuvee** ; `LLM : moyen domaine, moyen malveillance (non ancré : redescendu de fort)` ; cite MAL-2026-16141, T1546.018 |
| idna 3.20 | verdict **approuvee** ; `LLM : moyen code_inconnu (non ancré : redescendu de fort), moyen malicious_code, moyen credentials_in_files` |
| requests 2.34.2 | verdict **approuvee** ; `LLM : moyen faiblesses ×3` ; cite GHSA-x84v-xcm2-53pg |
| llm_demo 1.1 | conforme, aucun FORT (48 s) |
| llm_demo 1.2 | conforme ; `fort acces_secrets, exfiltration, dns, connexion, fichier_sensible` ; `cite : MAL-2025-191856, T1048, T1552.001` (61 s) |

**À surveiller :** la fausse alerte sur `requests` (`C-m3-reseau`) est apparue dans le **vrai
pipeline**, avec le rapport de la sandbox. `llm_paquet` passe sans sandbox. Le H16, sur une base
neuve, dira si `requests` et ses dépendances sont toutes publiées.

## Fait : la démo sur un domaine (préparation)
C a choisi `pipelad.tech`, chez OVHcloud :
- la **vitrine** sur `pipelad.tech` ;
- l'**interface de la plateforme** sur `demo.pipelad.tech`.

Les deux sont en HTTPS (Caddy, Let's Encrypt). L'interface reste derrière la connexion.

- `infra/aws/domaine.sh` :
  1. vérifie le DNS ;
  2. ouvre 80 et 443 au public sur la plateforme, et rien d'autre (SSH reste réservé à l'IP de
     l'admin ; le web reste sur `127.0.0.1:8000`) ;
  3. installe Caddy et la vitrine ;
  4. vérifie les deux URL.
- `infra/domaine/Caddyfile.modele` : en-têtes HSTS, `nosniff`, `X-Frame-Options DENY` ; CSP
  stricte sur la vitrine.
- `infra/domaine/vitrine/index.html` : une page statique, sans ressource extérieure. On y trouve
  le problème, le schéma, les étapes et les chiffres vérifiés (73 % et 0 fausse alerte en
  statique, 401, 8/8 en compromission), puis les principes et « et si la plateforme est
  compromise ? ».
- **Pas encore en ligne :** il faut d'abord que le domaine soit acheté et que sa zone DNS pointe
  sur la plateforme.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A (Sam) | La vitrine reprend le pitch (`docs/contexte.md`) : relire le texte, et le nom « Pipelad » | M3 | ok / retouches |
| A (Sam) | Derrière HTTPS : passer `https_only=True` au `SessionMiddleware` quand le web est servi en HTTPS (variable d'environnement ?). Le cookie de session n'a pas le drapeau `Secure` aujourd'hui | domaine public | ok / non |
| A (Sam) | Pas de limite aux essais de connexion : avec l'interface publique, un compte « jury » en rôle `dev` et des mots de passe longs ; une limite par IP serait mieux | domaine public | ok / non |
| B | Rien de bloquant : juste regarder `requests` pendant le H16 | H16 | — |

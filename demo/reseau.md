# Réseau de la démo (C) : schéma, preuves, « et si la plateforme est compromise ? », vidéo

Matière du M3 pour le deck (A) et pour la vidéo (C). Tout ce qui suit est **vérifié sur l'infra AWS**
(`infra/aws/verifier_h3.sh`, `verifier_m1.sh`, points `C-fin-m2` et `C-h16-preparation`).

## 1. Le schéma réseau (diapositive)

```
                           INTERNET
     pypi.org · api.osv.dev · flux RSS · API autorisées (api.github.com…)
                              ▲
                              │  la seule sortie ; ne part que nom + version de paquet
  ┌───────────────────────────┴──────────────────────────────┐
  │ SOUS-RÉSEAU PUBLIC 10.42.1.0/24                           │
  │ PLATEFORME AGRÉÉE 10.42.1.10                              │
  │  veille → délai 3 j → statique → sandbox → LLM + RAG      │
  │  → politique (le code décide) → signature Ed25519         │
  │  LLM, RAG, sandbox : tout local                           │
  └───────────────┬──────────────────────────▲───────────────┘
   :8443 TLS mutuel│ manifeste signé           │ :3129 relais d'API
   publier/révoquer│ + archives                │ (liste fermée)
  ┌───────────────▼──────────────────────────┴───────────────┐
  │ SOUS-RÉSEAU PRIVÉ 10.42.2.0/24 — aucune route vers Internet, DNS coupé │
  │ PASSERELLE 10.42.2.10                                     │
  │  récepteur : signature + hash + âge + nonce, sinon refus  │
  │  pypiserver :8080 (sans repli vers pypi.org) · relais :3128│
  └───────────────┬──────────────────────────────────────────┘
                  │ pip / API, réseau local seulement
  ┌───────────────▼──────────────────────────────────────────┐
  │ SERVEUR SENSIBLE 10.42.2.20 — aucun accès à Internet       │
  │  pip → passerelle:8080 · HTTPS_PROXY → passerelle:3128    │
  └──────────────────────────────────────────────────────────┘
```

**Légende en une ligne :** « Un seul passage vers Internet, et il est à nous. Le serveur n'installe que
ce qui a été vérifié et signé. »

## 2. Les barrières, et la preuve de chacune

| Barrière | Ce qui la tient | Preuve (commande de démo) |
|---|---|---|
| Le serveur n'a pas Internet | sous-réseau privé **sans route** (ni NAT, ni passerelle Internet) ; groupe de sécurité : sortie vers la passerelle seulement | `curl -m 5 https://pypi.org` échoue sur le serveur |
| Pas de fuite par DNS | DNS du VPC **coupé** ; noms internes dans `/etc/hosts` | `verifier_h3` contrôle 6 : aucune résolution |
| Rien qu'on n'a pas publié | pypiserver sans repli vers pypi.org | `pip install flask` : introuvable |
| Rien n'est publié sans signature | récepteur : Ed25519 + sha256 de chaque fichier + `emis_le` < 10 min + nonce unique ; dépôt écrit par le seul compte `recepteur` | `demo/forger.sh` → **401** |
| Seule la plateforme parle à la passerelle | TLS mutuel (certificat client exigé) ; `ufw` + groupe de sécurité : 8443 depuis la plateforme seulement | `curl` sans certificat : refusé |
| API sortantes contrôlées | relais CONNECT en liste fermée, sans déchiffrement, chaque demande journalisée | `api.github.com` → 200 ; `pypi.org` → 403 |
| La sandbox ne laisse rien sortir | réseau Docker interne + faux DNS/HTTP qui enregistrent ; leurres uniques par analyse ; traces signées par un jeton secret | 1.2 : DNS `collecte.attaquant-demo.invalid` vu, `~/.aws/credentials` (faux) lu |
| Le journal ne s'efface pas | append-only, chaîné par HMAC (clé hors base) | « Vérifier la chaîne » : intègre |
| On survit à une panne | `restic` local chiffré, sans les clés privées | base effacée puis restaurée : journal intact |

## 3. « Et si la plateforme est compromise ? » (diapositive)

C'est la question la plus probable du jury. Réponse honnête, en trois temps.

**Une plateforme usurpée** (un faux serveur, un attaquant sur le réseau) **ne peut rien publier** :
il lui faut le certificat client du lien **et** la clé de signature. C'est l'étape 4 de la démo.

**Une plateforme réellement prise** (l'attaquant y est root) :

| Elle peut… | Elle ne peut pas… |
|---|---|
| signer une version piégée avec la vraie clé : la passerelle l'acceptera | joindre Internet **depuis** le serveur ou la passerelle : il n'y a pas de route, c'est le réseau qui le dit, pas la plateforme |
| élargir la liste du relais d'API | lire les données du serveur : rien n'en sort vers la plateforme, sauf l'inventaire (noms et versions) |
| réécrire sa propre base | se connecter au serveur en SSH : la seule clé acceptée est sur le poste de l'admin, pas sur la plateforme |
| | effacer ses traces sur la passerelle : le registre des publications y est gardé, hors de sa portée |
| | modifier le journal sans que ce soit détecté, tant que la clé HMAC n'est pas volée |

**Ce qui limite les dégâts, dès le MVP :**
- la surface de la plateforme est petite : SSH et web depuis l'IP de l'admin seulement ;
- tout est local, donc aucune dépendance à un service cloud qui pourrait aussi être compromis ;
- la passerelle garde son propre registre de ce qui a été publié, et quand : après l'incident, on
  sait quelles versions retirer, et l'inventaire dit quels serveurs les ont téléchargées.

**Ce qui vient ensuite (feuille de route) :**
1. la **clé de signature hors de la plateforme** : YubiKey ou HSM, avec un geste humain pour signer ;
2. une **double signature** : le code de la plateforme, plus un admin, pour chaque publication ;
3. l'**ancre du journal** sur la passerelle : le dernier hash est porté par chaque manifeste, donc
   une réécriture côté plateforme est détectée (accord A et C, prévu après H16).

**Phrase de la diapositive :** « Prendre la plateforme ne donne ni Internet aux serveurs, ni leurs
données. Le pire possible est une publication signée, et la clé de signature quitte la plateforme
dans la version suivante. »

## 4. La vidéo (3 minutes au plus)

Enregistrée pendant la répétition H16, sur l'infra AWS, avec `demo/script.md` comme déroulé.
Écran partagé : navigateur à gauche, terminaux serveur et plateforme à droite.

| Temps | Plan | Ce qu'on voit | Voix |
|---|---|---|---|
| 0:00–0:15 | titre + schéma § 1 | les trois zones | « Vos serveurs n'installent que ce qu'on a vérifié. » |
| 0:15–0:35 | terminal serveur | `curl https://pypi.org` échoue ; `pip install requests` marche | « Ce serveur n'a pas Internet, et il installe pourtant ses paquets. » |
| 0:35–1:15 | navigateur | file d'attente : 1.1 attend son délai, puis analysée, approuvée, publiée ; `pip install -U` | « 3 jours d'attente en vrai : la plupart des versions piégées sont retirées dans ce délai. » |
| 1:15–2:05 | fiche de la 1.2 | bloquée ; preuves statiques ; sandbox (DNS de l'attaquant, faux secret lu) ; explication du LLM qui cite CWE-522 / T1552.005 | « Le code décide. L'IA explique, en citant des cas réels. » |
| 2:05–2:25 | terminal plateforme | `demo/forger.sh` → 401 | « Même usurpée, la plateforme ne publie rien sans la clé. » |
| 2:25–2:45 | navigateur | révocation, alerte dans l'inventaire, journal intègre | « Chaque décision est tracée, et rien ne s'efface. » |
| 2:45–3:00 | diapositive de mesure (B) | les trois colonnes | « Contrôles seuls, puis sandbox, puis IA : voici ce que chaque couche ajoute. » |

**Pour tenir 3 minutes :** les attentes du LLM (de 50 à 60 s par version sur CPU) sont coupées au
montage, avec un compteur visible. On ne montre jamais un résultat qui n'a pas eu lieu.

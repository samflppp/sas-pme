# Réseau de la démo (C) : schéma et « et si la plateforme est compromise ? »

Matière du M3 de C. Tout ce qui suit est **vérifié sur l'infra AWS** :
- `infra/aws/verifier_h3.sh` : le cloisonnement ;
- `infra/aws/verifier_m1.sh` : l'inventaire et le pare-feu ;
- `infra/aws/verifier_compromission.sh` : le § 3.

Le schéma en image : `demo/schema-reseau.svg`.

## 1. Le schéma réseau

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
  │ SOUS-RÉSEAU PRIVÉ 10.42.2.0/24 : aucune route vers Internet, DNS coupé │
  │ PASSERELLE 10.42.2.10                                     │
  │  récepteur : signature + hash + âge + nonce, sinon refus  │
  │  pypiserver :8080 (sans repli vers pypi.org) · relais :3128│
  └───────────────┬──────────────────────────────────────────┘
                  │ pip / API, réseau local seulement
  ┌───────────────▼──────────────────────────────────────────┐
  │ SERVEUR SENSIBLE 10.42.2.20 : aucun accès à Internet      │
  │  pip → passerelle:8080 · HTTPS_PROXY → passerelle:3128    │
  └──────────────────────────────────────────────────────────┘
```

**En une phrase :** « Un seul passage vers Internet, et il est à nous. Le serveur n'installe que ce
qui a été vérifié et signé. »

### Les flux autorisés, et rien d'autre

Groupes de sécurité AWS (`infra/aws/creer.sh`), doublés par `ufw` sur la passerelle :

| De → vers | Port | Pourquoi |
|---|---|---|
| poste de l'admin → plateforme | 22, 443 | administration, interface web (depuis son IP seulement) |
| plateforme → Internet | tout | la seule machine reliée à Internet |
| plateforme → passerelle | 8443 | récepteur : publier, révoquer, lire l'inventaire (TLS mutuel) |
| plateforme → passerelle, serveur | 22 | rebond SSH de l'admin ; **sa** clé n'est pas sur la plateforme |
| serveur → passerelle | 8080, 4873, 3128 | pip, npm (extension), relais d'API |
| passerelle → plateforme | 3129 | relais d'API, en liste fermée |
| serveur, passerelle → Internet | — | **aucune route** : ni NAT, ni passerelle Internet ; DNS du VPC coupé |

### Les barrières, et la preuve de chacune

| Barrière | Ce qui la tient | Preuve |
|---|---|---|
| Le serveur n'a pas Internet | sous-réseau privé **sans route** ; le serveur ne sort que vers la passerelle | `curl --noproxy '*' https://pypi.org` échoue sur le serveur |
| Pas de fuite par DNS | DNS du VPC **coupé** ; noms internes dans `/etc/hosts` | `verifier_h3` contrôle 6 : aucune résolution |
| Rien qu'on n'a pas publié | pypiserver sans repli vers pypi.org | `pip install flask` : introuvable |
| Rien n'est publié sans signature | le récepteur vérifie la signature Ed25519, le sha256 de chaque fichier, que `emis_le` a moins de 10 min et que le nonce est neuf ; seul le compte `recepteur` écrit dans le dépôt | `demo/forger.sh` → **401** |
| Seule la plateforme parle à la passerelle | TLS mutuel (certificat client exigé) ; 8443 ouvert pour la plateforme seulement | `curl` sans certificat : refusé |
| API sortantes contrôlées | relais CONNECT en liste fermée, sans déchiffrement, chaque demande journalisée | `api.github.com` → 200 ; `pypi.org` → 403 |
| La sandbox ne laisse rien sortir | réseau Docker interne, avec un faux DNS et un faux HTTP qui enregistrent ; leurres uniques par analyse ; traces signées par un jeton secret | 1.2 : DNS `collecte.attaquant-demo.invalid` vu, faux `~/.aws/credentials` lu |
| Le journal ne s'efface pas | append-only, chaîné par HMAC (clé hors de la base) | « Vérifier la chaîne » : intègre |
| On survit à une panne | `restic` local chiffré, sans les clés privées | base effacée puis restaurée : journal intact |

## 2. Trois attaquants, trois réponses

| Attaquant | Ce qu'il obtient |
|---|---|
| **Une version piégée** sur PyPI | rien : 3 jours de délai, puis l'analyse statique, la sandbox et la politique la bloquent avant la passerelle (démo 1.2) |
| **Une plateforme usurpée** (faux serveur, attaquant sur le réseau) | rien : il lui faut le certificat client du lien **et** la clé de signature (démo `forger.sh` → 401) |
| **La plateforme réellement prise** (l'attaquant y est root) | voir § 3 : beaucoup moins qu'on ne le croit, mais pas rien |

## 3. Et si la plateforme est compromise ?

C'est la question la plus probable du jury. La réponse honnête : **la plateforme est le point de
confiance du système**. Le réseau limite ce qu'un attaquant peut en faire.

### Ce qu'il peut faire

- **Signer une version piégée avec la vraie clé.** La clé de signature est sur la plateforme : la
  passerelle acceptera cette publication. C'est le risque principal.
- **Élargir la liste du relais d'API.** Un code déjà installé sur le serveur pourrait alors joindre
  un domaine de l'attaquant par ce relais.
- **Réécrire sa propre base et son interface** : verdicts, signaux, alertes affichées.
- **Faire installer une version qu'elle a signée** (démo seulement : agent d'installation du
  serveur, PR #95). Elle n'attend donc plus qu'un humain lance `pip install`. L'agent revérifie
  la signature, l'âge et le nonce, et n'installe que des **roues** (`--only-binary=:all:`) : aucun
  `setup.py` ne s'exécute à l'installation. Mais une roue piégée agit quand on l'importe, ou au
  prochain démarrage de Python par un fichier `.pth`. En production, cet agent n'existe pas : c'est
  l'équipe qui met à jour ses serveurs.

### Ce qu'il ne peut pas faire : vérifié sur AWS (`verifier_compromission.sh`, 8 contrôles OK)

| # | L'attaquant root sur la plateforme essaie… | Résultat | Contre-épreuve (le test sait réussir) |
|---|---|---|---|
| 1 | d'ouvrir une session SSH sur le **serveur**, avec chaque clé présente sur la plateforme | `Permission denied (publickey)` | sshd répond sur le port 22 : c'est la clé qui est refusée |
| 2 | d'ouvrir une session SSH sur la **passerelle**, pour réécrire le dépôt ou effacer le registre des publications | refusé | même contre-épreuve ; la clé du stub M0 a été retirée de la passerelle (C3) |
| 3 | d'écrire dans le dépôt sans passer par le récepteur (pypiserver :8080) | injoignable (`ufw`) | le serveur, lui, joint 8080 (code 200) |
| 4 | de joindre le serveur sur un autre port (80, 443, 8080) | rien n'écoute pour elle | le même test sur le port 22 répond |
| 5 | de faire sortir le **serveur** vers Internet, par adresse IP, sans DNS ni relais | aucune route | la plateforme, elle, joint `1.1.1.1` |
| 6 | de faire sortir la **passerelle** vers Internet | aucune route | idem |
| 7 | de faire passer le serveur vers un domaine hors liste par le relais | `403 Forbidden` | `api.github.com` par le même relais : 200 |
| 8 | (usurpée) de publier avec une autre clé | `401 signature invalide` | la vraie publication passe (démo 2) |

Ce que cela veut dire :
- **Les données du serveur restent sur le serveur.** Rien n'en sort vers la plateforme, sauf
  l'inventaire (des noms et des versions de paquets), et la plateforme ne peut pas s'y connecter.
- **Le cloisonnement ne dépend pas de la plateforme.** C'est la table de routage AWS qui le tient :
  la plateforme prise ne peut pas donner Internet au serveur ni à la passerelle.
- **Les traces sur la passerelle lui échappent.** Le registre des publications et des retraits y est
  gardé, hors de sa portée. Après l'incident, on sait quelles versions retirer, et l'inventaire dit
  quels serveurs les ont téléchargées.
- **Le journal de la plateforme** ne peut pas être modifié sans être détecté tant que la clé HMAC
  n'est pas volée. Root sur la plateforme peut la lire : c'est une limite, d'où le point 3
  ci-dessous.

### Ce qui vient ensuite (feuille de route)

1. **Sortir la clé de signature de la plateforme**, sur une YubiKey ou un HSM, avec un geste
   humain pour signer. Prendre la plateforme ne suffit plus pour publier.
2. **Double signature** : une publication exige la signature du code de la plateforme **et** celle
   d'un admin, depuis un autre appareil. La passerelle vérifie les deux.
3. **Ancrer le journal sur la passerelle** : chaque manifeste porte le dernier hash du journal, et la
   passerelle le garde. Une réécriture côté plateforme devient visible (accord A et C, prévu après
   H16).
4. **La liste du relais signée**, comme un manifeste. La passerelle refuse une liste qui n'est pas
   signée par l'admin.

**En une phrase :** « Prendre la plateforme ne donne ni Internet aux serveurs, ni leurs données, ni
une session sur leurs machines. Le pire possible est une publication signée, et la clé de signature
quitte la plateforme dans la version suivante. »

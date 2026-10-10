# infra (C) — démo AWS

```
Internet ── IGW ── 10.42.1.0/24 public : plateforme 10.42.1.10 (c7i.4xlarge, bastion SSH)
                   10.42.2.0/24 privé  : passerelle 10.42.2.10, serveur 10.42.2.20 (t3.small)
                                         table de routage = route « local » seule, pas de NAT
```

| Groupe | Entrée | Sortie |
|---|---|---|
| plateforme | 22, 443 depuis `MON_IP` | libre |
| passerelle | 22, 8443 depuis plateforme ; 8080, 4873, 3128 depuis serveur | 3129 vers plateforme |
| serveur | 22 depuis plateforme | 8080, 4873, 3128 vers passerelle |

## Utilisation

```bash
aws configure                     # identifiants AWS : jamais dans Git
cp infra/aws/config.env.exemple infra/aws/config.env   # régler MON_IP
infra/aws/creer.sh                # VPC, SG, clé (infra/secrets/, ignoré), 3 instances
infra/aws/installer.sh            # pypiserver + récepteur signé (TLS mutuel) sur la passerelle,
                                  # pip sur le serveur ; appelle certificats.sh
infra/aws/publier_manuel.sh requests   # test réseau seul, sans pipeline
infra/aws/verifier_h3.sh          # preuve H3
infra/aws/detruire.sh             # après chaque séance (la c7i.4xlarge coûte ~0,8 €/h)
ssh -F infra/secrets/ssh_config sas-serveur   # SSH via le bastion
```

Pas de GPU : notre compte n'a pas de quota « G and VT ». La plateforme est une `c7i.4xlarge`
(16 vCPU, 32 Go) ; le LLM local tourne sur CPU avec `qwen2.5-coder:3b` (`docs/architecture.md` § 7).
Il faut au moins 16 vCPU en « Running On-Demand Standard instances » dans la région choisie (us-east-1 pour le compte du workshop).

## Sans Internet, comment installer ?

La plateforme télécharge les wheels (`pip download`) et les copie sur la passerelle par `scp`. Là, pip
s'exécute depuis sa propre wheel (`python3 pip-X.whl/pip install --no-index --target …`). Le serveur
amorce pip de la même façon, depuis la wheel de pip publiée sur la passerelle.

pypiserver tourne avec `--disable-fallback` : un paquet absent renvoie 404, sans redirection vers
pypi.org. L'envoi (upload) est fermé : seule la plateforme publie, par copie dans `/srv/pypi/packages`.

## Le lien signé (M1)

- `certificats.sh` crée dans `infra/secrets/tls/` (hors Git) une petite autorité, le certificat
  serveur de la passerelle (`10.42.2.10`) et le certificat client de la plateforme. La clé de
  l'autorité reste sur le poste de C.
- La **clé de signature Ed25519 est créée sur la plateforme** (`~/sas/signature.pem`, 0600) et n'en
  sort jamais ; seule sa clé publique va sur la passerelle (`/etc/sas/plateforme_signature.pub`).
- Le récepteur (`passerelle.recepteur`, service `recepteur`) écoute sur `10.42.2.10:8443` et exige
  le certificat client. Il vérifie signature, hash, âge et nonce avant d'écrire dans le dépôt.
- `installer.sh` affiche les variables `SAS_PASSERELLE_URL`, `SAS_CLE_SIGNATURE`, `SAS_TLS_*` à
  donner au web. Sans `SAS_PASSERELLE_URL`, `publier()` reste sur le stub scp du M0.
- Démo H10 étape 3 : `demo/forger.sh` sur la plateforme ; la passerelle répond 401.

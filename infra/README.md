# infra (C) — démo AWS, M0

```
Internet ── IGW ── 10.42.1.0/24 public : plateforme 10.42.1.10 (g4dn.xlarge, bastion SSH)
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
infra/aws/installer.sh            # pypiserver sur la passerelle, pip sur le serveur
infra/aws/publier_manuel.sh requests   # test réseau seul, sans pipeline
infra/aws/verifier_h3.sh          # preuve H3
infra/aws/detruire.sh             # après chaque séance (la g4dn coûte cher)
ssh -F infra/secrets/ssh_config sas-serveur   # SSH via le bastion
```

Quota GPU : il faut au moins 4 vCPU en « Running On-Demand G and VT instances » dans eu-west-3.
Sinon, mettre `TYPE_PLATEFORME=c7i.4xlarge`.

## Sans Internet, comment installer ?

La plateforme télécharge les wheels (`pip download`) et les copie sur la passerelle par `scp`. Là, pip
s'exécute depuis sa propre wheel (`python3 pip-X.whl/pip install --no-index --target …`). Le serveur
amorce pip de la même façon, depuis la wheel de pip publiée sur la passerelle.

pypiserver tourne avec `--disable-fallback` : un paquet absent renvoie 404, sans redirection vers
pypi.org. L'envoi (upload) est fermé : seule la plateforme publie, par copie dans `/srv/pypi/packages`.

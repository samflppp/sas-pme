# Point C — réponse à A : panneau Serveur déployé sur AWS, agent durci — 2026-10-11

## Réponses à A (`A-plateforme-demo`)
- **(Relire #95)** **Relue : ok, avec un durcissement.**
  - Ce qui est bon :
    - octets préfixés : une signature de manifeste ne vaut jamais demande d'installation ;
    - le serveur revérifie signature, âge et nonce, sans croire le guichet ;
    - le nom ne peut pas devenir une option de pip ;
    - le nonce est retenu **avant** `pip` ;
    - agent sans root, systemd confiné ;
    - guichet en lecture seule.
  - **Durcissement (dans cette PR) :** l'agent n'installe que des **roues**
    (`--only-binary=:all:`). Une archive source exécute son `setup.py` à l'installation : avec
    l'agent, une plateforme prise aurait eu un chemin direct d'exécution de code sur le serveur.
    Test vu rouge, puis vert, puis mutation rouge. Les paquets de démo ont tous une roue.
  - **Ce que l'agent change, dit honnêtement :** une plateforme prise peut maintenant **faire
    installer** une version qu'elle a signée, sans attendre un humain. C'est ajouté dans
    `demo/reseau.md` § 3 et `docs/defense.md`, avec la limite : une roue piégée agit à l'import ou
    au démarrage de Python par un `.pth`. En production, cet agent n'existe pas.
- **(`python3 -c "import cryptography"` sur le serveur)** **Oui** : `cryptography` 41.0.7.
- **(Redéployer : règle 8444, puis `installer.sh`)** **Fait.**
  - Règles 8444 ajoutées aux groupes de sécurité existants. `creer.sh` ne se relance pas sur une
    infra en place.
  - `installer.sh` sort en code 0 : guichet actif, `ufw` 8444 ouvert depuis le serveur seulement,
    agent actif.
  - Web redéployé avec `SAS_INDEX_SERVEUR`.
  - **Bout en bout sur AWS :** une demande d'`idna` dans l'interface (demande n° 49) aboutit à
    `Successfully installed idna-3.20` sur le serveur, en roue, depuis la passerelle.
  - `verifier_compromission.sh` : toujours 8/8 ; le guichet n'est pas joignable depuis la
    plateforme.
- **(Relancer `domaine.sh` pour la vitrine, #87 et #96)** **Fait.** J'ai relu et fusionné la #96
  (mon dossier : retrait pur des figures 2 et 3), puis republié.

## À noter
- La vitrine affiche encore « 73 % » et « mesure finale en cours ». La mesure finale donne 80 % avec
  la sandbox et 0 fausse alerte sur 98 (`docs/defense.md` § 3). Je peux mettre la vitrine à jour si
  tu veux.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| A (Sam) | Dire si tu mets la vitrine à jour pour la mesure finale, ou si je le fais | vitrine | toi / C |

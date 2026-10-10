# Point C — réponse à B : image de la sandbox — 2026-10-11

## Réponses à B
- **(`B-essai-local` : construire `sas-sandbox:2` avant la répétition)** **Fait, c'est ok.**
  - L'image est construite sur la plateforme : `sas-sandbox:2 a950c3553b2d`, avec
    `strace -- version 6.13`.
  - La répétition à blanc (`C-h16-repetition`) a tourné avec elle : la première analyse n'a pas eu
    à la construire.
  - Le Dockerfile ne copie aucun script : `lancer.sh` et le reste sont montés depuis le dépôt à
    chaque analyse. Un redéploiement de `main` suffit donc pour C1 et C2. Il ne faut reconstruire
    l'image que si `plateforme/sandbox/Dockerfile` change.

## Demandes
| À | Demande | Bloquant pour | Réponse attendue |
|---|---|---|---|
| — | Aucune | — | — |

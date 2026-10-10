# Image de la sandbox : Python 3.12 (comme les serveurs) + de quoi construire un sdist hors ligne
# (le code de setup.py est un vecteur d'attaque : il doit s'exécuter ICI, sous surveillance).
FROM python:3.12-slim
# v2 : strace, pour voir aussi le code natif (fichiers lus, commandes, connexions).
RUN apt-get update -q && apt-get install -yq --no-install-recommends strace \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --no-cache-dir setuptools wheel && useradd --uid 10001 --no-create-home analyse

# Image de la sandbox : Python 3.12 (comme les serveurs) + de quoi construire un sdist hors ligne
# (le code de setup.py est un vecteur d'attaque : il doit s'exécuter ICI, sous surveillance).
FROM python:3.12-slim
RUN pip install --no-cache-dir setuptools wheel && useradd --uid 10001 --no-create-home analyse

"""Installation non éditable : les données du pipeline doivent suivre le paquet."""
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]


def test_la_liste_des_paquets_populaires_est_dans_package_data():
    config = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    motifs = config["tool"]["setuptools"]["package-data"]["plateforme.pipeline"]
    donnees = RACINE / "plateforme" / "pipeline"
    assert any(donnees.glob(m) for m in motifs)
    assert (donnees / "donnees" / "populaires_pypi.txt") in {f for m in motifs for f in donnees.glob(m)}

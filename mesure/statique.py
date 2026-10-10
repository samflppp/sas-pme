"""Mesure v1, contrôles statiques seuls (B) : le nom et le code, comme dans le pipeline.

Les échantillons malveillants (jeu de Datadog, zips chiffrés au mot de passe public « infected »)
sont **lus seulement** : déchiffrés en mémoire, leurs .py et .pth copiés dans une roue temporaire
le temps de l'analyse, puis effacés. Rien n'est installé, importé ni exécuté. À lancer avec
Python en `-I`, les échantillons dans un dossier à part (voir `mesurer.py`).
"""
import io
import posixpath
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from commun.modeles import Ecosysteme, Signal
from plateforme.pipeline.statique.code import TAILLE_MAX_FICHIER, controler_code
from plateforme.pipeline.statique.nom import controler_nom

MOT_DE_PASSE = b"infected"
_REPERES = {"PKG-INFO", "setup.py", "pyproject.toml", "setup.cfg"}
Telecharger = Callable[[str, str, Path], list[Path]]


def _info(nom: str) -> bool:
    n = PurePosixPath(nom).name
    return n.startswith("package_info-") and n.endswith(".json")


def _dedoubler(nom: str) -> str:
    """« a/b.py/a/b.py » (le jeu de données range parfois un fichier sous son propre chemin)."""
    parties = PurePosixPath(nom).parts
    for i in range(len(parties) - 1):
        queue = parties[i + 1:]
        if parties[i] == parties[-1] and parties[:i + 1][-len(queue):] == queue:
            return "/".join(parties[:i + 1])
    return nom


def chemins_relatifs(noms: list[str]) -> dict[str, str]:
    """{chemin dans l'échantillon : chemin dans le paquet}.

    Les échantillons sont des paquets dépliés sous des préfixes variés (`tmp/tmpXX/nom/`). On
    retrouve la racine du paquet, pour que `setup.py` et les `__init__.py` de premier niveau
    restent des points d'exécution, comme dans la vraie archive.
    """
    vrais = {n: _dedoubler(n) for n in noms if not n.endswith("/") and not _info(n)}
    fichiers = list(vrais.values())
    racines = set()
    for n in fichiers:
        parties = PurePosixPath(n).parts
        if parties[-1] in _REPERES:
            racines.add("/".join(parties[:-1]))
        racines.update("/".join(parties[:i]) for i, p in enumerate(parties[:-1])
                       if p.endswith(".dist-info"))
    racines.update(str(PurePosixPath(n).parent) for n in noms if _info(n))
    sortie, reste = {}, []
    for n in fichiers:
        sous = [r for r in racines if r in ("", ".") or n.startswith(r + "/")]
        if sous:
            r = max(sous, key=len)
            sortie[n] = n if r in ("", ".") else n[len(r) + 1:]
        else:
            reste.append(n)
    if reste:
        commun = posixpath.commonpath([posixpath.dirname(n) for n in reste]) if len(reste) > 1 \
            else posixpath.dirname(reste[0])
        sortie.update({n: posixpath.relpath(n, commun or ".") for n in reste})
    return {original: sortie[vrai] for original, vrai in vrais.items()}


def signaux_echantillon(eco: Ecosysteme, nom: str, version: str, echantillon: Path) -> list[Signal]:
    """Signaux du code d'un échantillon chiffré ; lève si l'échantillon est illisible."""
    with zipfile.ZipFile(echantillon) as z, tempfile.TemporaryDirectory() as tmp:
        z.setpassword(MOT_DE_PASSE)
        membres = [i for i in z.infolist() if not i.is_dir()]
        if len(membres) == 1 and membres[0].filename.endswith((".zip", ".whl")):
            z = zipfile.ZipFile(io.BytesIO(z.read(membres[0])))   # l'archive d'origine
            z.setpassword(MOT_DE_PASSE)
        relatifs = chemins_relatifs([i.filename for i in z.infolist()])
        # Roues (chemins gardés tels quels). Un échantillon garde parfois la roue ET les sources :
        # une copie déjà placée va dans la roue suivante, pour que les deux soient lues.
        copies: list[dict[str, bytes]] = []
        for info in z.infolist():
            rel = relatifs.get(info.filename)
            if rel and rel.endswith((".py", ".pth")) and info.file_size <= TAILLE_MAX_FICHIER:
                libre = next((c for c in copies if rel not in c), None)
                if libre is None:
                    copies.append(libre := {})
                libre[rel] = z.read(info)
        roues = []
        for i, fichiers in enumerate(copies):
            roues.append(Path(tmp) / f"{nom}-{version}-{i}-py3-none-any.whl")
            with zipfile.ZipFile(roues[-1], "w", zipfile.ZIP_DEFLATED) as sortie:
                for rel, octets in fichiers.items():
                    sortie.writestr(rel, octets)
        return controler_code(eco, nom, version, roues)


class Detecteur:
    """Pour `mesurer()` : nom + code. Malveillants : l'échantillon. Sains : la vraie archive de
    PyPI, comparée à la version précédente, comme le pipeline le fait pour une mise à jour."""

    def __init__(self, corpus: dict, *, echantillons: Path, telecharger: Telecharger,
                 cache: Path):
        self.entrees = {(e["nom"], e["version"]): e
                        for e in [*corpus["malveillants"], *corpus["sains"]]}
        self.echantillons, self.telecharger, self.cache = echantillons, telecharger, cache
        self.illisibles: dict[str, str] = {}
        self.sans_precedente: list[str] = []

    def __call__(self, eco: Ecosysteme, nom: str, version: str) -> list[Signal] | None:
        e = self.entrees[(nom, version)]
        try:
            if "echantillon" in e:
                code = signaux_echantillon(eco, nom, version, self.echantillons / e["echantillon"])
            else:
                archives = self.telecharger(nom, version, self.cache / nom / version)
                code = controler_code(eco, nom, version, archives,
                                      precedentes=self._precedentes(e))
        except Exception as erreur:  # noqa: BLE001 — une version illisible sort du compte
            self.illisibles[f"{nom} {version}"] = str(erreur)[:200]
            return None
        return controler_nom(eco, nom, version) + code

    def _precedentes(self, e: dict) -> list[Path] | None:
        avant = e.get("version_precedente")
        if not avant:
            return None
        try:
            return self.telecharger(e["nom"], avant, self.cache / e["nom"] / avant)
        except Exception:  # noqa: BLE001 — sans précédente, tout le code est analysé
            self.sans_precedente.append(f"{e['nom']} {avant}")
            return None


def detecteur(corpus: dict, *, echantillons: Path, telecharger: Telecharger,
              cache: Path) -> Detecteur:
    return Detecteur(corpus, echantillons=echantillons, telecharger=telecharger, cache=cache)

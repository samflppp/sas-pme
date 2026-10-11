"""Mesure, colonne « + sandbox » (B, M3) : chaque version du corpus passe dans la sandbox de C.

Les échantillons malveillants (jeu de Datadog, zips chiffrés « infected ») sont remis en archive
installable **sans rien exécuter ici** : déchiffrés, leurs fichiers recopiés tels quels dans
- un sdist s'il y a de quoi construire (`setup.py`, `pyproject.toml`) : le code de construction est
  un vecteur d'attaque, il doit tourner dans la sandbox, sous surveillance ;
- sinon une roue (celle d'origine si l'échantillon la contient ; ses fichiers de dist-info gardés,
  son RECORD réécrit pour que pip l'accepte ; une dist-info minimale s'il n'y en a pas).
Seule la sandbox (`plateforme.sandbox.executer`, conteneur sans réseau réel) les installe et les
importe, avec le même module que le pipeline (`nom` avec « _ »). Les sains : la vraie archive de
PyPI, la roue d'abord, comme le pipeline. Chaque rapport est gardé en JSON dans le cache : une
seconde mesure, ou la colonne LLM sur la plateforme, ne relance pas la sandbox.
"""
import base64
import hashlib
import importlib.util
import io
import posixpath
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from commun.modeles import Ecosysteme, RapportSandbox

_spec = importlib.util.spec_from_file_location(
    "statique_mesure", Path(__file__).resolve().parent / "statique.py")
statique = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(statique)

Executer = Callable[..., RapportSandbox]


def _dist_info(noms) -> str | None:
    return next((PurePosixPath(n).parts[0] for n in noms
                 if len(PurePosixPath(n).parts) > 1
                 and PurePosixPath(n).parts[0].endswith(".dist-info")), None)


def _hash(octets: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(octets).digest()).rstrip(b"=").decode()


def _roue(fichiers: dict[str, bytes], nom: str, version: str, dossier: Path) -> Path:
    info = _dist_info(fichiers) or f"{nom.replace('-', '_')}-{version}.dist-info"
    fichiers = {n: o for n, o in fichiers.items() if n != f"{info}/RECORD"}
    fichiers.setdefault(f"{info}/METADATA",
                        f"Metadata-Version: 2.1\nName: {nom}\nVersion: {version}\n".encode())
    fichiers.setdefault(f"{info}/WHEEL", b"Wheel-Version: 1.0\nGenerator: sas-pme-mesure\n"
                                         b"Root-Is-Purelib: true\nTag: py3-none-any\n")
    record = [f"{n},{_hash(o)},{len(o)}" for n, o in fichiers.items()] + [f"{info}/RECORD,,"]
    fichiers[f"{info}/RECORD"] = ("\n".join(record) + "\n").encode()
    chemin = dossier / f"{info.removesuffix('.dist-info')}-py3-none-any.whl"
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
        for n, o in fichiers.items():
            z.writestr(n, o)
    return chemin


def _sdist(fichiers: dict[str, bytes], nom: str, version: str, dossier: Path) -> Path:
    racine = f"{nom}-{version}"
    chemin = dossier / f"{racine}.tar.gz"
    with tarfile.open(chemin, "w:gz") as t:
        for n, o in fichiers.items():
            info = tarfile.TarInfo(f"{racine}/{n}")
            info.size, info.mode = len(o), 0o644
            t.addfile(info, io.BytesIO(o))
    return chemin


def reemballer(echantillon: Path, nom: str, version: str, dossier: Path) -> Path:
    """L'archive installable d'un échantillon chiffré, écrite dans `dossier` (lue, jamais exécutée)."""
    dossier.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(echantillon) as z:
        z.setpassword(statique.MOT_DE_PASSE)
        membres = [i for i in z.infolist() if not i.is_dir()]
        if len(membres) == 1 and membres[0].filename.endswith((".zip", ".whl")):
            octets = z.read(membres[0])
            z = zipfile.ZipFile(io.BytesIO(octets))
            z.setpassword(statique.MOT_DE_PASSE)
            if (info := _dist_info(z.namelist())):
                chemin = dossier / f"{info.removesuffix('.dist-info')}-py3-none-any.whl"
                chemin.write_bytes(octets)
                return chemin
        noms = [i.filename for i in z.infolist()]
        relatifs = statique.chemins_relatifs(noms)
        if not any(PurePosixPath(r).name in ("setup.py", "pyproject.toml") or ".dist-info/" in r
                   for r in relatifs.values()):
            # Sans repère, le préfixe commun retiré emporterait le dossier du paquet : on le garde.
            vrais = [n for n in relatifs]
            commun = posixpath.commonpath([posixpath.dirname(n) for n in vrais]) if vrais else ""
            base = posixpath.dirname(commun)
            relatifs = {n: posixpath.relpath(n, base or ".") for n in vrais}
        fichiers = {relatifs[i.filename]: z.read(i) for i in z.infolist()
                    if i.filename in relatifs and not relatifs[i.filename].startswith("..")}
    if "setup.py" in fichiers or "pyproject.toml" in fichiers:
        return _sdist(fichiers, nom, version, dossier)
    return _roue(fichiers, nom, version, dossier)


class Executeur:
    """Pour la mesure : le rapport de sandbox d'une version du corpus, gardé dans le cache."""

    def __init__(self, corpus: dict, *, echantillons: Path, cache: Path, executer: Executer,
                 archives_saines: Callable[[str, str], list[Path]]):
        self.entrees = {(e["nom"], e["version"]): e
                        for e in [*corpus["malveillants"], *corpus["sains"]]}
        self.echantillons, self.cache = echantillons, cache
        self.executer, self.archives_saines = executer, archives_saines

    def __call__(self, eco: Ecosysteme, nom: str, version: str) -> RapportSandbox:
        garde = self.cache / "rapports" / f"{nom}-{version}.json"
        if garde.is_file():
            return RapportSandbox.model_validate_json(garde.read_text(encoding="utf-8"))
        e = self.entrees[(nom, version)]
        if "echantillon" in e:
            archive = reemballer(self.echantillons / e["echantillon"], nom, version,
                                 self.cache / "archives" / f"{nom}-{version}")
        else:
            archives = self.archives_saines(nom, version)
            archive = ([a for a in archives if a.suffix == ".whl"] or archives)[0]
        rapport = self.executer(eco, archive, nom.replace("-", "_"))
        garde.parent.mkdir(parents=True, exist_ok=True)
        garde.write_text(rapport.model_dump_json(), encoding="utf-8")
        return rapport

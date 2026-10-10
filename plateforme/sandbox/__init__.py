"""Sandbox v1 (C), docs/contrats.md § 3 et docs/architecture.md § 5.

Chaque analyse a son réseau Docker **interne** (aucune route vers Internet). Il ne contient que :
  - le piège (`piege.py`) : faux DNS qui répond à tout, faux serveurs TCP/HTTP qui notent tout ;
  - la cible : lecture seule sauf /tmp, aucune capacité, sans root, mémoire et processus bornés,
    faux secrets (variables et fichiers) dont chaque valeur est unique à l'analyse.
La cible installe l'archive sans réseau, importe le module, attend un battement. Le rapport
rassemble le traceur (dans la cible) et le journal du piège (hors de portée du paquet).

Réglages : SAS_SANDBOX=stub (rapport vide, pour les tests), SAS_SANDBOX_IMAGE (défaut sas-sandbox:2,
construite au besoin depuis le Dockerfile voisin), SAS_SANDBOX_ATTENTE (secondes après la fin de l'import, défaut 60 : un battement).
"""

import json
import os
import secrets
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from commun.modeles import Ecosysteme, RapportSandbox
from plateforme.sandbox import rapport

__all__ = ["Ecosysteme", "RapportSandbox", "executer", "commande_cible"]

ICI = Path(__file__).parent
HOME = "/tmp/home"
UTILISATEUR = "10001:10001"
ATTENTE_PAR_DEFAUT_S = 60          # v2 : observer un battement après l'import
LEURRES_ENV = ("AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "NPM_TOKEN")
LEURRES_FICHIERS = {"L_AWS": "~/.aws/credentials", "L_SSH": "~/.ssh/id_rsa", "L_NPMRC": "~/.npmrc",
                    "L_PYPIRC": "~/.pypirc", "L_GIT": "~/.git-credentials"}


def _vide() -> RapportSandbox:
    return RapportSandbox(requetes_dns=[], connexions=[], fichiers_sensibles=[], leurres_lus=[],
                          processus=[], code_sortie=0, duree_s=0.0, delai_depasse=False)


def _docker(*args: str, timeout: float = 60, verifier: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout,
                          check=verifier)


def commande_cible(nom: str, reseau: str, image: str, dossier: str, archive: str, module: str,
                   attente_s: int, leurres: dict[str, str]) -> list[str]:
    cmd = ["docker", "run", "--name", nom, "--network", reseau, "--hostname", "srv-prod",
           "--read-only", "--tmpfs", "/tmp:rw,exec,mode=1777,size=512m",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "--pids-limit", "256", "--memory", "1g", "--cpus", "2", "--user", UTILISATEUR,
           "-v", f"{dossier}/entree:/entree:ro", "-v", f"{dossier}/outils:/outils:ro",
           "-v", f"{dossier}/journal:/journal", "-v", f"{dossier}/resolv.conf:/etc/resolv.conf:ro",
           "-e", f"HOME={HOME}", "-e", f"SAS_ARCHIVE={archive}", "-e", f"SAS_MODULE={module}",
           "-e", f"SAS_ATTENTE={attente_s}"]
    for cle, valeur in leurres.items():
        cmd += ["-e", f"{cle}={valeur}"]
    return cmd + [image, "sh", "/outils/lancer.sh"]


def _image() -> str:
    image = os.environ.get("SAS_SANDBOX_IMAGE", "sas-sandbox:2")
    if _docker("image", "inspect", image, verifier=False).returncode != 0:
        _docker("build", "-q", "-t", image, str(ICI), timeout=600)
    return image


MAX_LIGNES = 2_000_000                 # au-delà, le journal est tronqué et c'est un signal (B, C1)
MAX_LIGNE = 65536
LIGNE_TRONQUEE = '{"t": "tronque"}'


def _lire(chemin: Path) -> list[str]:
    """Tout le journal, ligne par ligne (pas de plafond en octets qui laisserait une fuite tardive
    hors du rapport, B : C1). Un lien symbolique posé par le paquet n'est pas suivi (B : C7)."""
    try:
        fd = os.open(chemin, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return []
    lignes: list[str] = []
    with os.fdopen(fd, "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            return []
        for brute in f:
            if len(lignes) >= MAX_LIGNES:
                lignes.append(LIGNE_TRONQUEE)
                break
            lignes.append(brute[:MAX_LIGNE].decode("utf-8", "replace").rstrip("\n"))
    return lignes


def _code(dossier: Path) -> int:
    for nom in ("code_installation", "code_import"):
        try:
            code = int((dossier / nom).read_text().strip())
        except (OSError, ValueError):
            return -1
        if code:
            return code
    return 0


def _attendre_piege(journal: Path, delai_s: float = 20) -> str:
    fin = time.monotonic() + delai_s
    while time.monotonic() < fin:
        for ligne in _lire(journal):
            if '"pret"' in ligne:
                return json.loads(ligne)["ip"]
        time.sleep(0.2)
    raise RuntimeError("le piège réseau de la sandbox n'a pas démarré")


def _analyser(archive: Path, module: str, duree_max_s: int) -> RapportSandbox:
    image = _image()
    ident = secrets.token_hex(4)
    reseau, piege, cible = f"sas-sb-{ident}", f"sas-piege-{ident}", f"sas-cible-{ident}"
    attente = int(os.environ.get("SAS_SANDBOX_ATTENTE", str(ATTENTE_PAR_DEFAUT_S)))
    valeurs = {nom: "sasleurre" + secrets.token_hex(12) for nom in (*LEURRES_ENV, *LEURRES_FICHIERS)}
    env_cible = {n: valeurs[n] for n in LEURRES_ENV} | {n: valeurs[n] for n in LEURRES_FICHIERS}
    env_cible["L_ID"] = secrets.token_hex(8).upper()
    a_chercher = {n: valeurs[n] for n in LEURRES_ENV} | \
        {LEURRES_FICHIERS[n]: valeurs[n] for n in LEURRES_FICHIERS}

    with tempfile.TemporaryDirectory(prefix="sas-sandbox-") as tmp:
        # Les conteneurs tournent sans aucune capacité : même leur root est un « autre » pour ces
        # dossiers. Lecture seule pour les entrées ; écriture pour les deux journaux seulement.
        d = Path(tmp)
        d.chmod(0o711)
        for sous, mode in (("entree", 0o755), ("outils", 0o755), ("journal", 0o777),
                           ("piege", 0o777)):
            (d / sous).mkdir()
            (d / sous).chmod(mode)
        copies = [(archive, d / "entree" / archive.name), (ICI / "piege.py", d / "piege" / "piege.py")]
        copies += [(f, d / "outils" / f.name) for f in (ICI / "trace").iterdir() if f.is_file()]
        for source, cible_ in copies:
            shutil.copyfile(source, cible_)
            cible_.chmod(0o644)

        _docker("network", "create", "--internal", reseau)
        debut, depasse = time.monotonic(), False
        try:
            _docker("run", "-d", "--name", piege, "--network", reseau, "--read-only",
                    "--cap-drop", "ALL", "--cap-add", "NET_BIND_SERVICE", "--memory", "256m",
                    "--pids-limit", "128", "-v", f"{d}/piege:/piege", image,
                    "python", "/piege/piege.py", "/piege/reseau.jsonl")
            ip = _attendre_piege(d / "piege" / "reseau.jsonl")
            (d / "resolv.conf").write_text(f"nameserver {ip}\n")
            (d / "resolv.conf").chmod(0o644)
            debut = time.monotonic()
            try:
                subprocess.run(commande_cible(cible, reseau, image, str(d), archive.name, module,
                                              attente, env_cible),
                               capture_output=True, timeout=duree_max_s)
            except subprocess.TimeoutExpired:
                depasse = True
                _docker("kill", cible, verifier=False)
            duree = time.monotonic() - debut
            time.sleep(0.5)          # dernières lignes du piège
        finally:
            _docker("rm", "-f", cible, piege, verifier=False)
            _docker("network", "rm", reseau, verifier=False)

        return rapport.construire(
            trace=_lire(d / "journal" / "trace.jsonl"), reseau=_lire(d / "piege" / "reseau.jsonl"),
            leurres=a_chercher, home=HOME, code_sortie=_code(d / "journal"), duree_s=duree,
            delai_depasse=depasse, ip_piege=ip,
            strace_installation=_lire(d / "journal" / "strace_installation.txt"),
            strace_import=_lire(d / "journal" / "strace_import.txt"))


def executer(ecosysteme: Ecosysteme, archive: Path, module: str,
             duree_max_s: int = 120) -> RapportSandbox:
    archive = Path(archive)
    if not archive.is_file():
        raise FileNotFoundError(archive)
    if os.environ.get("SAS_SANDBOX") == "stub":
        return _vide()
    if str(ecosysteme) != "pypi":
        raise NotImplementedError("sandbox v1 : pip seulement")
    return _analyser(archive.resolve(), module, duree_max_s)

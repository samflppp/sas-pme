"""Contrôles sur le code d'une version : lu en mémoire depuis les archives, jamais extrait sur
disque ni exécuté (docs/organisation.md § 7).

Où regarder : là où le code s'exécute sans qu'on l'appelle (`setup.py` à l'installation, `.pth`
au démarrage de Python, `__init__.py` de premier niveau à l'import). Le reste du paquet n'est lu
que pour le code obfusqué et les domaines d'exfiltration, pour éviter les fausses alertes d'un
client réseau légitime.

Avec les archives de la version précédente, seul ce qui est **nouveau** compte (diff).

Les tests du paquet (`tests/`, `test_*.py`, `conftest.py`) ne sont pas lus : ils ne s'installent
ni ne s'exécutent chez le client, et ils regorgent d'adresses et de faux secrets.
"""
import ipaddress
import re
import tarfile
import zipfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from commun.modeles import Ecosysteme, Niveau, Signal, Source

TAILLE_MAX_FICHIER = 20_000_000     # octets ; au-delà, le fichier n'est pas lu (et on le dit)
TAILLE_MAX_TOTALE = 200_000_000     # contre une bombe de décompression
EXTRAIT_MAX = 200

# Commande ou réseau : FORT. exec/eval/cmdclass seuls (lire la version, étendre « install ») : MOYEN.
_INSTALLATION = re.compile(
    r"\b(subprocess\.\w+\(|os\.system\(|os\.popen\(|os\.exec\w*\(|socket\.socket\(|urlopen\(|"
    r"requests\.(get|post|put)\(|http\.client\.|httpx\.\w+\(|gethostbyname)")
_PERSONNALISE = re.compile(r"(\bexec\(|\beval\(|\bcmdclass\s*=?)")
_EXEC = re.compile(r"\b(exec|eval|compile)\s*\(")
_DECODE = re.compile(r"(b64decode|b32decode|a85decode|b85decode|decompress|marshal\.loads|"
                     r"codecs\.decode|bytes\.fromhex|\[::-1\])")
_BASE64 = re.compile(r"""['"][A-Za-z0-9+/]{300,}={0,2}['"]""")
_SECRETS = re.compile(r"(\.aws/credentials|\.ssh/id_|\.npmrc|\.pypirc|\.git-credentials|"
                      r"/etc/shadow|AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN|NPM_TOKEN|PYPI_TOKEN|"
                      r"os\.environ\.copy\(\)|dict\(os\.environ\))")
_RESEAU = re.compile(r"(urlopen\(|requests\.\w+\(|http\.client\.|socket\.|gethostbyname|"
                     r"getaddrinfo|httpx\.\w+\(|\bcurl\b|\bwget\b)")
_URL = re.compile(r"https?://([A-Za-z0-9.-]+)(:\d+)?[^\s'\"]*")
_EXFIL = ("ngrok.io", "ngrok-free.app", "ngrok.app", "pastebin.com", "transfer.sh",
          "webhook.site", "requestbin.net", "pipedream.net", "api.telegram.org", "interact.sh",
          "oast.fun", "oast.pro", "burpcollaborator.net", "discordapp.com")


def _texte(nom: str) -> bool:
    p = PurePosixPath(nom)
    if p.name == "conftest.py" or p.name.startswith("test_") \
            or {"tests", "test", "testing"} & set(p.parts[:-1]):
        return False
    return nom.endswith((".py", ".pth"))


def _ip_publique(hote: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(hote)
        return ip.is_global and not ip.is_multicast
    except ValueError:
        return False


def _lire(archive: Path) -> Iterator[tuple[str, str | None]]:
    """(chemin dans l'archive, texte) des .py et .pth ; texte None si trop gros. Rien n'est écrit."""
    total = 0
    source = not archive.name.endswith(".whl")  # sdist : on retire le dossier « nom-version/ »

    def chemin(nom: str) -> str:
        parties = PurePosixPath(nom).parts
        return "/".join(parties[1:] if source and len(parties) > 1 else parties)

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if info.is_dir() or not _texte(info.filename):
                    continue
                total += info.file_size
                if info.file_size > TAILLE_MAX_FICHIER or total > TAILLE_MAX_TOTALE:
                    yield chemin(info.filename), None
                    continue
                yield chemin(info.filename), z.read(info).decode("utf-8", "replace")
        return
    with tarfile.open(archive, "r:*") as t:
        for m in t:
            if not m.isreg() or not _texte(m.name):   # ni lien, ni périphérique
                continue
            total += m.size
            if m.size > TAILLE_MAX_FICHIER or total > TAILLE_MAX_TOTALE:
                yield chemin(m.name), None
                continue
            yield chemin(m.name), t.extractfile(m).read().decode("utf-8", "replace")


def _point_d_execution(fichier: str) -> bool:
    p = PurePosixPath(fichier)
    return (fichier == "setup.py" or p.suffix == ".pth"
            or (p.name == "__init__.py" and len(p.parts) <= 3))


def _extrait(ligne: str) -> str:
    ligne = ligne.strip()
    return ligne if len(ligne) <= EXTRAIT_MAX else ligne[:EXTRAIT_MAX - 1] + "…"


def _hotes_suspects(ligne: str) -> Iterator[str]:
    if "discord.com/api/webhooks" in ligne:
        yield "discord.com"
    for m in _URL.finditer(ligne):
        hote = m.group(1).lower()
        if _ip_publique(hote) or hote.endswith(_EXFIL):
            yield hote


def _constats(fichier: str, texte: str) -> Iterator[tuple[str, Niveau, int, str, dict]]:
    """(sorte, niveau, ligne, extrait, preuve en plus) ; une seule fois par sorte et fichier."""
    lignes = texte.splitlines()
    execution = _point_d_execution(fichier)
    vus: set[str] = set()

    def premiere(sorte: str, niveau: Niveau, regle) -> Iterator:
        for i, l in enumerate(lignes, 1):
            if regle(l):
                yield sorte, niveau, i, _extrait(l), {}
                return

    if fichier == "setup.py":
        fort = list(premiere("code_installation", Niveau.FORT, _INSTALLATION.search))
        yield from fort or premiere("setup_personnalise", Niveau.MOYEN, _PERSONNALISE.search)
    if fichier.endswith(".pth"):
        imports = [l for l in lignes if l.lstrip().startswith("import")]
        yield from premiere("code_installation", Niveau.FORT, lambda l: l in imports and (
            _INSTALLATION.search(l) or _RESEAU.search(l) or _EXEC.search(l)))
        if not any(_INSTALLATION.search(l) or _RESEAU.search(l) or _EXEC.search(l)
                   for l in imports):
            yield from premiere("pth_import", Niveau.MOYEN, lambda l: l in imports)
    yield from premiere("exec_obfusque", Niveau.FORT,
                        lambda l: _EXEC.search(l) and _DECODE.search(l))
    yield from premiere("bloc_base64", Niveau.MOYEN, _BASE64.search)
    for i, l in enumerate(lignes, 1):
        for hote in _hotes_suspects(l):
            if hote not in vus:
                vus.add(hote)
                yield "domaine_suspect", Niveau.FORT, i, _extrait(l), {"domaine": hote}
    if not execution:
        return
    yield from premiere("acces_secrets", Niveau.FORT, _SECRETS.search)
    secret = next((i for i, l in enumerate(lignes, 1) if _SECRETS.search(l)), None)
    reseau = next((i for i, l in enumerate(lignes, 1) if _RESEAU.search(l)), None)
    if secret and reseau:
        yield ("exfiltration", Niveau.BLOQUANT, reseau, _extrait(lignes[reseau - 1]),
               {"ligne_secret": secret, "extrait_secret": _extrait(lignes[secret - 1])})
    for i, l in enumerate(lignes, 1):
        for m in _URL.finditer(l):
            hote = m.group(1).lower()
            if hote not in vus:
                vus.add(hote)
                yield "domaine", Niveau.INFO, i, _extrait(l), {"domaine": hote}


def _analyser(archives: list[Path]) -> list[tuple[str, Niveau, str, int, str, dict]]:
    trouves, cles = [], set()
    for archive in archives:
        try:
            for fichier, texte in _lire(archive):
                if texte is None:
                    trouves.append(("fichier_ignore", Niveau.MOYEN, fichier, 0,
                                    f"{fichier} trop gros pour être lu", {}))
                    continue
                for sorte, niveau, ligne, extrait, plus in _constats(fichier, texte):
                    cle = (sorte, fichier, extrait)
                    if cle not in cles:      # roue et source portent souvent le même fichier
                        cles.add(cle)
                        trouves.append((sorte, niveau, fichier, ligne, extrait, plus))
        except (tarfile.TarError, zipfile.BadZipFile, OSError, EOFError) as e:
            trouves.append(("archive_illisible", Niveau.FORT, archive.name, 0,
                            f"{archive.name} illisible : {e}"[:EXTRAIT_MAX], {}))
    return trouves


def controler_code(eco: Ecosysteme, nom: str, version: str, archives: list[Path], *,
                   precedentes: list[Path] | None = None) -> list[Signal]:
    """Signaux STATIQUE sur le code ; avec `precedentes`, seulement ce qui est nouveau.

    Pour npm, les règles sont celles de `code_npm.py` (scripts de package.json, JavaScript)."""
    if eco is Ecosysteme.NPM:
        from plateforme.pipeline.statique import code_npm
        analyser = code_npm.analyser
    else:
        analyser = _analyser
    deja = {(t[0], t[2], t[4]) for t in analyser(precedentes)} if precedentes else set()
    signaux = []
    for sorte, niveau, fichier, ligne, extrait, plus in analyser(archives):
        if (sorte, fichier, extrait) in deja:
            continue
        preuve = {"fichier": fichier, "ligne": ligne, "extrait": extrait,
                  "nouveau": True if precedentes else None, **plus}
        signaux.append(Signal(ecosysteme=eco, nom=nom, version=version, source=Source.STATIQUE,
                              niveau=niveau, sorte=sorte, preuve=preuve))
    return signaux

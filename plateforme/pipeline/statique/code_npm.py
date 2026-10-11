"""Contrôles sur le code d'une version npm : l'archive `.tgz` est lue en mémoire, jamais extraite
sur disque ni exécutée (docs/organisation.md § 7). Le pendant npm de `code.py`.

Où regarder : là où le code s'exécute sans qu'on l'appelle.
- Les scripts `preinstall`, `install` et `postinstall` de `package.json`, lancés par `npm install`
  (le ver Shai-Hulud passait par là), et les fichiers JavaScript qu'ils lancent (`node x.js`).
- Le fichier principal (`main`, sinon `index.js`), exécuté au premier `require`.
Le reste du paquet n'est lu que pour le code obfusqué et les domaines d'exfiltration.

Ne sont pas lus : `node_modules/`, les tests (`test/`, `tests/`, `__tests__/`, `*.test.js`,
`*.spec.js`), qui ne s'exécutent pas chez le client.
"""
import json
import re
import shlex
import tarfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from commun.modeles import Niveau
from plateforme.pipeline.statique.code import (
    EXTRAIT_MAX, TAILLE_MAX_FICHIER, TAILLE_MAX_TOTALE, _BASE64, _URL, _extrait, _hotes_suspects,
)

SCRIPTS_INSTALLATION = ("preinstall", "install", "postinstall")
_JS = (".js", ".cjs", ".mjs")
# Script de package.json qui télécharge, ouvre un shell ou décode : FORT.
_SCRIPT_DANGEREUX = re.compile(r"(\bcurl\b|\bwget\b|\bbash\b|\bsh\s+-c\b|powershell|https?://|"
                               r"base64|\beval\b|\|\s*(ba)?sh\b)", re.IGNORECASE)
# Dans un fichier lancé à l'installation : commande ou réseau, FORT.
_INSTALLATION = re.compile(r"(child_process|\bexecSync\(|\bspawnSync?\(|\bexecFile\w*\(|"
                           r"https?\.(get|request)\(|\bfetch\(|net\.connect|dns\.(lookup|resolve))")
# eval, Function ou vm qui reçoivent directement du texte décodé (base64, hex, codes de caractères).
# Le décodage doit être l'argument : dans un fichier minifié, tout tient sur une ligne, et un eval
# et un atob sans rapport s'y côtoient (json5, prisma, next).
_EXEC_DECODE = re.compile(
    r"(\beval|\bFunction|vm\.run\w*)\s*\(\s*(Buffer\.from\([^)]{0,200}['\"](base64|hex)['\"]|"
    r"atob\(|String\.fromCharCode\(|[\w$.]{1,40}\.split\(['\"]['\"]\)\.reverse\(\))")
_COMMENTAIRE = re.compile(r"^\s*(//|/\*|\*)")
_SECRETS = re.compile(r"(\.aws/credentials|\.ssh/id_|\.npmrc|\.pypirc|\.git-credentials|"
                      r"/etc/shadow|AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN|NPM_TOKEN|"
                      r"JSON\.stringify\(\s*process\.env\s*\))")
_RESEAU = re.compile(r"(https?\.(get|request)\(|require\(['\"]https?['\"]\)\.(get|request)|"
                     r"\bfetch\(|net\.connect|dns\.(lookup|resolve)|\baxios\b|XMLHttpRequest|"
                     r"new\s+WebSocket|\bcurl\b|\bwget\b)")


def _lu(nom: str) -> bool:
    p = PurePosixPath(nom)
    if {"node_modules", "test", "tests", "__tests__"} & set(p.parts[:-1]):
        return False
    if p.name.endswith((".test.js", ".spec.js", ".test.mjs", ".spec.mjs")):
        return False
    return p.name == "package.json" or p.suffix in _JS


def _lire(archive: Path) -> Iterator[tuple[str, str | None]]:
    """(chemin dans le paquet, texte) ; texte None si trop gros. Rien n'est écrit sur disque."""
    total = 0
    with tarfile.open(archive, "r:*") as t:
        for m in t:
            parties = PurePosixPath(m.name).parts
            if not m.isreg() or len(parties) < 2:     # ni lien, ni périphérique
                continue
            chemin = "/".join(parties[1:])            # « package/ » (ou autre racine) retiré
            if not _lu(chemin):
                continue
            total += m.size
            if m.size > TAILLE_MAX_FICHIER or total > TAILLE_MAX_TOTALE:
                yield chemin, None
                continue
            yield chemin, t.extractfile(m).read().decode("utf-8", "replace")


def _fichiers_lances(script: str) -> set[str]:
    """Les fichiers JavaScript qu'un script lance (`node a.js`, `node ./b/c.js`)."""
    try:
        mots = shlex.split(script)
    except ValueError:
        mots = script.split()
    return {str(PurePosixPath(m.removeprefix("./"))) for m in mots if m.endswith(_JS)}


def _principal(paquet: dict) -> str:
    main = paquet.get("main") if isinstance(paquet.get("main"), str) else "index.js"
    main = str(PurePosixPath(main.removeprefix("./")))
    return main if main.endswith(_JS) else f"{main}.js"


def _constats_paquet(paquet: dict) -> Iterator[tuple[str, Niveau, str, int, str, dict]]:
    scripts = paquet.get("scripts") if isinstance(paquet.get("scripts"), dict) else {}
    for nom in SCRIPTS_INSTALLATION:
        script = scripts.get(nom)
        if not isinstance(script, str) or not script.strip():
            continue
        extrait = _extrait(f'"{nom}": "{script}"')
        if _SCRIPT_DANGEREUX.search(script):
            yield "code_installation", Niveau.FORT, "package.json", 0, extrait, {"script": nom}
        else:
            yield "script_installation", Niveau.MOYEN, "package.json", 0, extrait, {"script": nom}


def _constats_fichier(fichier: str, texte: str, lance: bool, principal: bool
                      ) -> Iterator[tuple[str, Niveau, int, str, dict]]:
    lignes = texte.splitlines()
    vus: set[str] = set()

    def premiere(sorte: str, niveau: Niveau, regle) -> Iterator:
        for i, l in enumerate(lignes, 1):
            if regle(l):
                yield sorte, niveau, i, _extrait(l), {}
                return

    if lance:
        yield from premiere("code_installation", Niveau.FORT, _INSTALLATION.search)
    yield from premiere("exec_obfusque", Niveau.FORT, _EXEC_DECODE.search)
    yield from premiere("bloc_base64", Niveau.MOYEN, _BASE64.search)
    for i, l in enumerate(lignes, 1):
        if _COMMENTAIRE.match(l):      # une adresse citée en commentaire n'est pas appelée
            continue
        for hote in _hotes_suspects(l):
            if hote not in vus:
                vus.add(hote)
                yield "domaine_suspect", Niveau.FORT, i, _extrait(l), {"domaine": hote}
    if not (lance or principal):
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


def analyser(archives: list[Path]) -> list[tuple[str, Niveau, str, int, str, dict]]:
    """Constats (sorte, niveau, fichier, ligne, extrait, preuve en plus), au format de `code.py`."""
    trouves, cles = [], set()

    def ajouter(t: tuple) -> None:
        cle = (t[0], t[2], t[4])
        if cle not in cles:
            cles.add(cle)
            trouves.append(t)

    for archive in archives:
        try:
            textes = dict(_lire(archive))
            try:
                paquet = json.loads(textes.get("package.json") or "{}")
            except ValueError:
                paquet = {}
            paquet = paquet if isinstance(paquet, dict) else {}
            for t in _constats_paquet(paquet):
                ajouter(t)
            scripts = paquet.get("scripts") if isinstance(paquet.get("scripts"), dict) else {}
            lances = set().union(*(_fichiers_lances(s) for n, s in scripts.items()
                                   if n in SCRIPTS_INSTALLATION and isinstance(s, str)))
            principal = _principal(paquet)
            for fichier, texte in textes.items():
                if fichier == "package.json":
                    continue
                if texte is None:
                    ajouter(("fichier_ignore", Niveau.MOYEN, fichier, 0,
                             f"{fichier} trop gros pour être lu", {}))
                    continue
                for sorte, niveau, ligne, extrait, plus in _constats_fichier(
                        fichier, texte, fichier in lances, fichier == principal):
                    ajouter((sorte, niveau, fichier, ligne, extrait, plus))
        except (tarfile.TarError, OSError, EOFError) as e:
            ajouter(("archive_illisible", Niveau.FORT, archive.name, 0,
                     f"{archive.name} illisible : {e}"[:EXTRAIT_MAX], {}))
    return trouves

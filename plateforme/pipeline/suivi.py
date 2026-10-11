"""Suivi en direct de la pipeline (A, conception-demo § 2) : chaque étape d'une analyse, à un rappel
(la page « Direct » de la plateforme) et au journal chaîné.

`traiter(..., suivi=rappel)` appelle `rappel(sujet, etape, etat, detail)` :
- `etat` vaut « debut », « fin », « erreur », ou « flux » (un morceau de l'explication du LLM) ;
- `sujet` est « pypi:nom@version », comme au journal.
Les fins et les erreurs sont aussi journalisées (action `etape`) : elles restent auditables. Les
débuts et les morceaux du LLM ne vont qu'au rappel. Un rappel qui plante ne change rien à l'analyse.
"""
import json
import re
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from commun.modeles import Version
from plateforme.db.acces import Base

Rappel = Callable[[str, str, str, dict], None]


def sujet(v: Version) -> str:
    return f"{v.ecosysteme.value}:{v.nom}@{v.version}"


class Etapes:
    def __init__(self, base: Base, v: Version, rappel: Rappel | None):
        self._base, self._rappel, self.sujet = base, rappel, sujet(v)

    def _dire(self, etape: str, etat: str, detail: dict) -> None:
        if self._rappel is None:
            return
        try:
            self._rappel(self.sujet, etape, etat, detail)
        except Exception as e:  # noqa: BLE001 — l'affichage ne doit jamais arrêter l'analyse
            print(f"[sas-pme] suivi : {e!r}", file=sys.stderr)

    @contextmanager
    def etape(self, nom: str) -> Iterator[dict]:
        """`with etapes.etape("sandbox") as detail:` ; ce qui est mis dans `detail` part avec la fin."""
        detail: dict = {}
        self._dire(nom, "debut", {})
        t0 = time.monotonic()
        try:
            yield detail
        except Exception as e:
            fin = {**detail, "duree_s": round(time.monotonic() - t0, 2),
                   "erreur": f"{type(e).__name__}: {e}"[:300]}
            self._base.journaliser("pipeline", "etape", self.sujet,
                                   {**fin, "etape": nom, "etat": "erreur"})
            self._dire(nom, "erreur", fin)
            raise
        fin = {**detail, "duree_s": round(time.monotonic() - t0, 2)}
        self._base.journaliser("pipeline", "etape", self.sujet, {**fin, "etape": nom, "etat": "fin"})
        self._dire(nom, "fin", fin)

    def flux(self, nom: str, explication: str) -> None:
        self._dire(nom, "flux", {"explication": explication})


# Les étapes de la version en cours d'analyse : le LLM du pipeline y écrit ses morceaux sans que
# la signature des fonctions injectées (tests de B) change.
_courantes: ContextVar[Etapes | None] = ContextVar("etapes_courantes", default=None)


@contextmanager
def pour(base: Base, v: Version, rappel: Rappel | None) -> Iterator[Etapes]:
    etapes = Etapes(base, v, rappel)
    jeton = _courantes.set(etapes)
    try:
        yield etapes
    finally:
        _courantes.reset(jeton)


def morceau_llm() -> Callable[[str], None] | None:
    """Pour `llm.analyser(morceau=...)` : None hors d'une analyse suivie (pas de flux)."""
    etapes = _courantes.get()
    return None if etapes is None or etapes._rappel is None else (lambda t: etapes.flux("ia", t))


_DEBUT = re.compile(r'"explication"\s*:\s*"')


def explication_partielle(brut: str) -> str:
    """Le texte du champ « explication » d'un JSON encore en cours d'écriture, échappements décodés.
    Un échappement coupé en fin de morceau attend le morceau suivant."""
    m = _DEBUT.search(brut)
    if m is None:
        return ""
    sortie, i = [], m.end()
    while i < len(brut):
        c = brut[i]
        if c == '"':
            break
        if c == "\\":
            sequence = brut[i:i + 6] if brut[i + 1:i + 2] == "u" else brut[i:i + 2]
            if len(sequence) < (6 if brut[i + 1:i + 2] == "u" else 2):
                break                            # échappement incomplet : au prochain morceau
            try:
                sortie.append(json.loads(f'"{sequence}"'))
            except ValueError:
                break
            i += len(sequence)
            continue
        sortie.append(c)
        i += 1
    return "".join(sortie)

"""Versions et plages npm (semver 2.0, règles de node-semver), sans dépendance externe.

Le pipeline npm s'en sert pour trier les versions d'un paquet, écarter les préversions et choisir la
version mûre d'une dépendance dans sa plage (`^1.2.0`, `~1.2`, `>=1 <2`, `1.x`, `a - b`, `||`).
Une plage hors semver (étiquette `latest`, URL git, `file:`, alias `npm:`) est refusée : la demande
échoue plutôt que d'installer une version qu'aucune règle ne désigne.
"""
import re

_VERSION = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                      r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?$")
_PARTIELLE = re.compile(r"^v?(\d+|[xX*])(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?"
                        r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?$")
_JOKER = {"x", "X", "*"}

Lue = tuple[int, int, int, tuple]


def _pre(texte: str | None) -> tuple:
    return tuple(int(p) if p.isdigit() else p for p in texte.split(".")) if texte else ()


def lire(version: str) -> Lue | None:
    """(majeure, mineure, correctif, préversion), ou None si ce n'est pas une version semver."""
    m = _VERSION.match(version.strip())
    if not m:
        return None
    return int(m[1]), int(m[2]), int(m[3]), _pre(m[4])


def _cle(lue: Lue) -> tuple:
    maj, mi, pa, pre = lue
    # Une préversion passe avant la version finale ; un identifiant numérique avant un texte.
    return (maj, mi, pa, 0 if pre else 1,
            tuple((0, p, "") if isinstance(p, int) else (1, 0, p) for p in pre))


def cle(version: str) -> tuple:
    """Clé de tri ; lève ValueError pour une version illisible."""
    lue = lire(version)
    if lue is None:
        raise ValueError(f"version npm illisible : {version!r}")
    return _cle(lue)


def preversion(version: str) -> bool:
    lue = lire(version)
    return bool(lue and lue[3])


class Plage:
    """Une plage de versions npm ; `contient(version)` dit si la version y entre."""

    def __init__(self, texte: str):
        self.texte = texte
        brut = texte.strip()
        self.ensembles = [self._ensemble(a.strip()) for a in brut.split("||")] if brut else [[]]

    # Un comparateur : (opérateur, version lue, écrit par l'auteur ?). Les bornes déduites
    # (« <2.0.0-0 » pour ^1.2.3) n'autorisent pas les préversions ; seules celles écrites le font.
    def _ensemble(self, alternative: str) -> list[tuple[str, Lue, bool]]:
        if not alternative and self.texte.strip():
            raise ValueError(f"plage npm illisible : {self.texte!r}")
        h = re.fullmatch(r"(\S+)\s+-\s+(\S+)", alternative)
        if h:
            bas, haut = self._partielle(h[1]), self._partielle(h[2])
            return [*self._superieur_ou_egal(bas), *self._inferieur_ou_egal(haut)]
        comparateurs = []
        for jeton in re.sub(r"(>=|<=|>|<|=|\^|~)\s+", r"\1", alternative).split():
            m = re.fullmatch(r"(>=|<=|>|<|=|\^|~)?(.+)", jeton)
            op, partielle = m[1] or "", self._partielle(m[2])
            comparateurs += self._traduire(op, partielle)
        return comparateurs

    def _partielle(self, texte: str) -> tuple:
        m = _PARTIELLE.match(texte)
        if not m:
            raise ValueError(f"plage npm illisible : {self.texte!r}")
        nombres = [None if (p is None or p in _JOKER) else int(p) for p in m.group(1, 2, 3)]
        # Après un joker, tout le reste est joker (« 1.x.3 » vaut « 1.x »).
        for i in range(1, 3):
            if nombres[i - 1] is None:
                nombres[i] = None
        return (*nombres, _pre(m[4]))

    @staticmethod
    def _plein(p: tuple) -> Lue:
        return (p[0] or 0, p[1] or 0, p[2] or 0, p[3])

    def _superieur_ou_egal(self, p: tuple) -> list:
        return [] if p[0] is None else [(">=", self._plein(p), bool(p[3]))]

    def _inferieur_ou_egal(self, p: tuple) -> list:
        maj, mi, pa, pre = p
        if maj is None:
            return []
        if mi is None:
            return [("<", (maj + 1, 0, 0, (0,)), False)]
        if pa is None:
            return [("<", (maj, mi + 1, 0, (0,)), False)]
        return [("<=", (maj, mi, pa, pre), bool(pre))]

    def _traduire(self, op: str, p: tuple) -> list:
        maj, mi, pa, pre = p
        if op in ("", "="):
            if maj is None:
                return []
            if pa is None:   # « 1.x », « 1.2 » : une plage, pas une version exacte
                return [*self._superieur_ou_egal(p), *self._inferieur_ou_egal(p)]
            return [("=", (maj, mi, pa, pre), bool(pre))]
        if op == ">=":
            return self._superieur_ou_egal(p)
        if op == "<=":
            return self._inferieur_ou_egal(p)
        if op == ">":
            if maj is None:
                return [("<", (0, 0, 0, (0,)), False)]       # « >* » : rien
            if mi is None:
                return [(">=", (maj + 1, 0, 0, ()), False)]
            if pa is None:
                return [(">=", (maj, mi + 1, 0, ()), False)]
            return [(">", (maj, mi, pa, pre), bool(pre))]
        if op == "<":
            return [] if maj is None else [("<", self._plein(p), bool(pre))]
        if op == "~":
            if maj is None:
                return []
            haut = (maj + 1, 0, 0, (0,)) if mi is None else (maj, mi + 1, 0, (0,))
            return [(">=", self._plein(p), bool(pre)), ("<", haut, False)]
        # « ^ » : ne change pas le premier nombre non nul.
        if maj is None:
            return []
        if maj > 0 or mi is None:
            haut = (maj + 1, 0, 0, (0,))
        elif mi > 0 or pa is None:
            haut = (0, mi + 1, 0, (0,))
        else:
            haut = (0, 0, pa + 1, (0,))
        return [(">=", self._plein(p), bool(pre)), ("<", haut, False)]

    def contient(self, version: str) -> bool:
        v = lire(version)
        if v is None:
            return False
        return any(self._satisfait(v, ensemble) for ensemble in self.ensembles)

    @staticmethod
    def _satisfait(v: Lue, ensemble: list) -> bool:
        cv = _cle(v)
        tests = {"=": lambda a, b: a == b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
                 ">": lambda a, b: a > b, "<": lambda a, b: a < b}
        if not all(tests[op](cv, _cle(borne)) for op, borne, _ in ensemble):
            return False
        # Une préversion n'entre que si l'auteur a écrit une préversion du même x.y.z.
        return not v[3] or any(ecrit and borne[3] and borne[:3] == v[:3]
                               for _, borne, ecrit in ensemble)

"""Accès à la base de la plateforme (A). B et la page web passent par ici ; personne d'autre ne fait de SQL.

Contrat : docs/contrats.md § 2. Chaque changement d'état, chaque verdict et chaque version détectée
écrit une entrée dans le journal chaîné.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path

from commun.modeles import (
    Ecosysteme, EntreeInventaire, Etat, RapportSandbox, Signal, Verdict, Version,
)

DELAI_PAR_DEFAUT = timedelta(days=3)
_SCHEMA = Path(__file__).with_name("schema.sql")
_GENESE = "0" * 64
_SCRYPT = (2**14, 8, 1)  # n, r, p : 16 Mo et quelques dizaines de ms par essai


class Role(StrEnum):
    ADMIN = "admin"  # tout, plus les comptes et (M1) la décision humaine
    DEV = "dev"      # catalogue, fiches, demander un paquet


@dataclass(frozen=True)
class Compte:
    identifiant: str
    role: Role
    actif: bool
    doit_changer: bool
    derniere_connexion: datetime | None


@dataclass(frozen=True)
class EntreeJournal:
    seq: int
    a: datetime
    acteur: str
    action: str
    sujet: str
    charge: dict


@dataclass(frozen=True)
class Fiche:
    version: Version
    raison: str
    signaux: list[Signal]
    verdict: Verdict | None
    verdict_id: int | None
    rapport_sandbox: RapportSandbox | None


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat()


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _cle(eco: Ecosysteme, nom: str, version: str) -> str:
    return f"{eco.value}:{nom}@{version}"


def _empreinte(mot_de_passe: str) -> str:
    n, r, p = _SCRYPT
    sel = os.urandom(16)
    h = hashlib.scrypt(mot_de_passe.encode("utf-8"), salt=sel, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${sel.hex()}${h.hex()}"


def _verifier_empreinte(mot_de_passe: str, empreinte: str) -> bool:
    _, n, r, p, sel, h = empreinte.split("$")
    calcule = hashlib.scrypt(mot_de_passe.encode("utf-8"), salt=bytes.fromhex(sel), n=int(n),
                             r=int(r), p=int(p), dklen=len(h) // 2)
    return hmac.compare_digest(calcule.hex(), h)


_EMPREINTE_LEURRE = _empreinte("leurre")  # même coût pour un identifiant inconnu


def _hash(prec: str, a: str, acteur: str, action: str, sujet: str, charge: str) -> str:
    corps = json.dumps([a, acteur, action, sujet, charge], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256((prec + corps).encode("utf-8")).hexdigest()


class Base:
    def __init__(self, chemin: str):
        self._verrou = threading.Lock()
        self._c = sqlite3.connect(chemin, check_same_thread=False, isolation_level=None)
        self._c.row_factory = sqlite3.Row
        self._c.execute("PRAGMA journal_mode=WAL")
        self._c.executescript(_SCHEMA.read_text(encoding="utf-8"))

    # --- versions -------------------------------------------------------------
    def enregistrer_version(self, v: Version, acteur: str = "pipeline") -> bool:
        """True si la version est nouvelle."""
        with self._verrou:
            cur = self._c.execute(
                "INSERT OR IGNORE INTO versions VALUES (?,?,?,?,?,?,?,?)",
                (v.ecosysteme.value, v.nom, v.version, _iso(v.publiee_le), _iso(v.detectee_le),
                 v.etat.value, "", _iso(_maintenant())))
            nouvelle = cur.rowcount == 1
            if nouvelle:
                self._journaliser(acteur, "version_detectee", _cle(v.ecosysteme, v.nom, v.version),
                                  {"publiee_le": _iso(v.publiee_le), "etat": v.etat.value})
            return nouvelle

    def lire_version(self, eco: Ecosysteme, nom: str, version: str) -> Version | None:
        r = self._c.execute("SELECT * FROM versions WHERE ecosysteme=? AND nom=? AND version=?",
                            (eco.value, nom, version)).fetchone()
        return self._version(r) if r else None

    def lister_versions(self, etat: Etat | None = None) -> list[Version]:
        if etat is None:
            rows = self._c.execute("SELECT * FROM versions ORDER BY maj_le DESC").fetchall()
        else:
            rows = self._c.execute("SELECT * FROM versions WHERE etat=? ORDER BY maj_le DESC",
                                   (etat.value,)).fetchall()
        return [self._version(r) for r in rows]

    def lister_avec_raison(self, etats: list[Etat]) -> list[tuple[Version, str]]:
        """Versions dans ces états, avec la raison de leur dernier changement, par date de publication."""
        marques = ",".join("?" * len(etats))
        rows = self._c.execute(f"SELECT * FROM versions WHERE etat IN ({marques}) ORDER BY publiee_le",
                               [e.value for e in etats]).fetchall()
        return [(self._version(r), r["raison"]) for r in rows]

    def versions_a_traiter(self, maintenant: datetime,
                           delai: timedelta = DELAI_PAR_DEFAUT) -> list[Version]:
        """Versions en attente dont le délai depuis la publication est écoulé."""
        limite = _iso(maintenant - delai)
        rows = self._c.execute(
            "SELECT * FROM versions WHERE etat=? AND publiee_le<=? ORDER BY publiee_le",
            (Etat.EN_ATTENTE.value, limite)).fetchall()
        return [self._version(r) for r in rows]

    def changer_etat(self, eco: Ecosysteme, nom: str, version: str, etat: Etat, raison: str,
                     acteur: str = "pipeline") -> None:
        with self._verrou:
            cur = self._c.execute(
                "UPDATE versions SET etat=?, raison=?, maj_le=? "
                "WHERE ecosysteme=? AND nom=? AND version=?",
                (etat.value, raison, _iso(_maintenant()), eco.value, nom, version))
            if cur.rowcount == 0:
                raise KeyError(_cle(eco, nom, version))
            self._journaliser(acteur, "etat_change", _cle(eco, nom, version),
                              {"etat": etat.value, "raison": raison})

    # --- signaux, verdicts, rapports -----------------------------------------
    def ajouter_signal(self, s: Signal) -> int:
        with self._verrou:
            cur = self._c.execute(
                "INSERT INTO signaux (ecosysteme, nom, version, donnees, cree_le) VALUES (?,?,?,?,?)",
                (s.ecosysteme.value, s.nom, s.version, s.model_dump_json(), _iso(_maintenant())))
            return cur.lastrowid

    def enregistrer_verdict(self, eco: Ecosysteme, nom: str, version: str, v: Verdict,
                            acteur: str = "pipeline") -> int:
        """Renvoie l'identifiant du verdict, repris dans le manifeste signé."""
        with self._verrou:
            cur = self._c.execute(
                "INSERT INTO verdicts (ecosysteme, nom, version, donnees, cree_le) VALUES (?,?,?,?,?)",
                (eco.value, nom, version, v.model_dump_json(), _iso(_maintenant())))
            self._journaliser(acteur, "verdict", _cle(eco, nom, version),
                              {"verdict_id": cur.lastrowid, "etat": v.etat.value, "raison": v.raison})
            return cur.lastrowid

    def enregistrer_rapport_sandbox(self, eco: Ecosysteme, nom: str, version: str,
                                    r: RapportSandbox) -> None:
        with self._verrou:
            self._c.execute(
                "INSERT INTO rapports_sandbox (ecosysteme, nom, version, donnees, cree_le) "
                "VALUES (?,?,?,?,?)",
                (eco.value, nom, version, r.model_dump_json(), _iso(_maintenant())))

    def fiche(self, eco: Ecosysteme, nom: str, version: str) -> Fiche | None:
        r = self._c.execute("SELECT * FROM versions WHERE ecosysteme=? AND nom=? AND version=?",
                            (eco.value, nom, version)).fetchone()
        if r is None:
            return None
        cle = (eco.value, nom, version)
        signaux = [Signal.model_validate_json(x["donnees"]) for x in self._c.execute(
            "SELECT donnees FROM signaux WHERE ecosysteme=? AND nom=? AND version=? ORDER BY id", cle)]
        v = self._c.execute("SELECT id, donnees FROM verdicts WHERE ecosysteme=? AND nom=? AND version=? "
                            "ORDER BY id DESC LIMIT 1", cle).fetchone()
        rs = self._c.execute("SELECT donnees FROM rapports_sandbox WHERE ecosysteme=? AND nom=? "
                             "AND version=? ORDER BY id DESC LIMIT 1", cle).fetchone()
        return Fiche(
            version=self._version(r), raison=r["raison"], signaux=signaux,
            verdict=Verdict.model_validate_json(v["donnees"]) if v else None,
            verdict_id=v["id"] if v else None,
            rapport_sandbox=RapportSandbox.model_validate_json(rs["donnees"]) if rs else None)

    # --- inventaire ----------------------------------------------------------
    def enregistrer_inventaire(self, entrees: list[EntreeInventaire]) -> None:
        """Remplace l'instantané précédent par celui lu sur la passerelle."""
        with self._verrou:
            self._c.execute("BEGIN")
            self._c.execute("DELETE FROM inventaire")
            self._c.executemany(
                "INSERT INTO inventaire VALUES (?,?,?,?,?)",
                [(e.ecosysteme.value, e.nom, e.version, e.telechargements,
                  _iso(e.dernier) if e.dernier else None) for e in entrees])
            self._c.execute("COMMIT")

    def inventaire(self) -> list[tuple[Ecosysteme, str, str]]:
        return [(Ecosysteme(r["ecosysteme"]), r["nom"], r["version"]) for r in self._c.execute(
            "SELECT ecosysteme, nom, version FROM inventaire ORDER BY ecosysteme, nom, version")]

    # --- comptes ------------------------------------------------------------
    def creer_compte(self, identifiant: str, role: Role, mot_de_passe: str, *, acteur: str,
                     doit_changer: bool = True) -> Compte:
        """ValueError si l'identifiant existe déjà."""
        with self._verrou:
            try:
                self._c.execute(
                    "INSERT INTO comptes (identifiant, empreinte, role, doit_changer, cree_le) "
                    "VALUES (?,?,?,?,?)", (identifiant, _empreinte(mot_de_passe), Role(role).value,
                                           int(doit_changer), _iso(_maintenant())))
            except sqlite3.IntegrityError:
                raise ValueError(f"le compte {identifiant!r} existe déjà") from None
            self._journaliser(acteur, "compte_cree", f"compte:{identifiant}", {"role": role.value})
        return self.lire_compte(identifiant)

    def authentifier(self, identifiant: str, mot_de_passe: str) -> Compte | None:
        """Le compte si le mot de passe est bon et le compte actif ; sinon None."""
        r = self._c.execute("SELECT empreinte, actif FROM comptes WHERE identifiant = ?",
                            (identifiant,)).fetchone()
        bon = _verifier_empreinte(mot_de_passe, r["empreinte"] if r else _EMPREINTE_LEURRE)
        if r is None or not bon or not r["actif"]:
            return None
        with self._verrou:
            self._c.execute("UPDATE comptes SET derniere_connexion = ? WHERE identifiant = ?",
                            (_iso(_maintenant()), identifiant))
        return self.lire_compte(identifiant)

    def lire_compte(self, identifiant: str) -> Compte | None:
        r = self._c.execute("SELECT * FROM comptes WHERE identifiant = ?", (identifiant,)).fetchone()
        return self._compte(r) if r else None

    def lister_comptes(self) -> list[Compte]:
        return [self._compte(r) for r in
                self._c.execute("SELECT * FROM comptes ORDER BY identifiant")]

    def changer_role(self, identifiant: str, role: Role, *, acteur: str) -> None:
        """ValueError si on retirerait le dernier admin actif ; KeyError si le compte est inconnu."""
        with self._verrou:
            avant = self._exiger_compte(identifiant)
            if avant["role"] == Role.ADMIN and role is not Role.ADMIN:
                self._garder_un_admin(identifiant)
            self._c.execute("UPDATE comptes SET role = ? WHERE identifiant = ?",
                            (Role(role).value, identifiant))
            self._journaliser(acteur, "compte_role", f"compte:{identifiant}",
                              {"de": avant["role"], "vers": role.value})

    def desactiver(self, identifiant: str, *, acteur: str) -> None:
        """ValueError si c'est le dernier admin actif ; KeyError si le compte est inconnu."""
        with self._verrou:
            avant = self._exiger_compte(identifiant)
            if avant["role"] == Role.ADMIN:
                self._garder_un_admin(identifiant)
            self._c.execute("UPDATE comptes SET actif = 0 WHERE identifiant = ?", (identifiant,))
            self._journaliser(acteur, "compte_desactive", f"compte:{identifiant}", {})

    def changer_mot_de_passe(self, identifiant: str, nouveau: str, *, acteur: str,
                             doit_changer: bool = False) -> None:
        with self._verrou:
            self._exiger_compte(identifiant)
            self._c.execute("UPDATE comptes SET empreinte = ?, doit_changer = ? WHERE identifiant = ?",
                            (_empreinte(nouveau), int(doit_changer), identifiant))
            self._journaliser(acteur, "compte_mot_de_passe", f"compte:{identifiant}",
                              {"doit_changer": doit_changer})

    def _exiger_compte(self, identifiant: str) -> sqlite3.Row:
        r = self._c.execute("SELECT * FROM comptes WHERE identifiant = ?", (identifiant,)).fetchone()
        if r is None:
            raise KeyError(identifiant)
        return r

    def _garder_un_admin(self, sauf: str) -> None:
        autres = self._c.execute(
            "SELECT COUNT(*) FROM comptes WHERE role = 'admin' AND actif = 1 AND identifiant != ?",
            (sauf,)).fetchone()[0]
        if autres == 0:
            raise ValueError("il doit rester au moins un admin actif")

    @staticmethod
    def _compte(r: sqlite3.Row) -> Compte:
        dc = r["derniere_connexion"]
        return Compte(r["identifiant"], Role(r["role"]), bool(r["actif"]), bool(r["doit_changer"]),
                      datetime.fromisoformat(dc) if dc else None)

    # --- journal -------------------------------------------------------------
    def journaliser(self, acteur: str, action: str, sujet: str, charge: dict) -> None:
        """Pour une action qui n'est pas déjà journalisée ici (connexion, décision humaine…)."""
        with self._verrou:
            self._journaliser(acteur, action, sujet, charge)

    def journal(self, limite: int = 500) -> list[EntreeJournal]:
        rows = self._c.execute("SELECT * FROM journal ORDER BY seq LIMIT ?", (limite,)).fetchall()
        return [EntreeJournal(r["seq"], datetime.fromisoformat(r["a"]), r["acteur"], r["action"],
                              r["sujet"], json.loads(r["charge"])) for r in rows]

    def verifier_journal(self) -> tuple[bool, int | None]:
        """(intègre, seq de la première entrée qui casse la chaîne)."""
        prec = _GENESE
        for r in self._c.execute("SELECT * FROM journal ORDER BY seq"):
            attendu = _hash(prec, r["a"], r["acteur"], r["action"], r["sujet"], r["charge"])
            if r["prec"] != prec or r["hash"] != attendu:
                return False, r["seq"]
            prec = r["hash"]
        return True, None

    def _journaliser(self, acteur: str, action: str, sujet: str, charge: dict) -> None:
        dernier = self._c.execute("SELECT hash FROM journal ORDER BY seq DESC LIMIT 1").fetchone()
        prec = dernier["hash"] if dernier else _GENESE
        a = _iso(_maintenant())
        texte = json.dumps(charge, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self._c.execute(
            "INSERT INTO journal (a, acteur, action, sujet, charge, prec, hash) VALUES (?,?,?,?,?,?,?)",
            (a, acteur, action, sujet, texte, prec, _hash(prec, a, acteur, action, sujet, texte)))

    @staticmethod
    def _version(r: sqlite3.Row) -> Version:
        return Version(ecosysteme=Ecosysteme(r["ecosysteme"]), nom=r["nom"], version=r["version"],
                       publiee_le=datetime.fromisoformat(r["publiee_le"]),
                       detectee_le=datetime.fromisoformat(r["detectee_le"]), etat=Etat(r["etat"]))

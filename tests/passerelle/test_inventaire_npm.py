"""Inventaire npm de la passerelle : téléchargements d'archives lus dans le journal de Verdaccio."""
from datetime import datetime, timezone

from commun.modeles import Ecosysteme
from passerelle.inventaire_npm import inventaire, telechargement


def ligne(url: str, status: int = 200, ip: str = "10.42.2.20", ms: int = 1791716700000,
          methode: str = "GET") -> str:
    return ('{"level":25,"time":%d,"request":{"method":"%s","url":"%s"},"remoteIP":"%s",'
            '"status":%d,"msg":"x"}' % (ms, methode, url, ip, status))


def test_un_get_d_archive_reussi_est_un_telechargement():
    t = telechargement(ligne("/@org/outil/-/outil-1.2.0.tgz"))
    assert (t.nom, t.version, t.ip) == ("@org/outil", "1.2.0", "10.42.2.20")
    assert t.quand == datetime.fromtimestamp(1791716700, tz=timezone.utc)
    assert telechargement(ligne("/@org%2foutil/-/outil-1.2.0.tgz")).nom == "@org/outil"
    assert telechargement(ligne("/left-pad/-/left-pad-1.3.0.tgz")).version == "1.3.0"


def test_ni_index_ni_erreur_ni_ligne_illisible_ne_comptent():
    for l in (ligne("/@org%2foutil"), ligne("/left-pad/-/left-pad-1.3.0.tgz", status=404),
              ligne("/left-pad/-/left-pad-1.3.0.tgz", methode="PUT"),
              ligne("/left-pad/-/autre-1.0.0.tgz"), "pas du json", '{"msg": "démarrage"}'):
        assert telechargement(l) is None


def test_versions_presentes_et_revoquees_deja_telechargees():
    registre = ["2026-10-11T09:00:00+00:00 publie npm:left-pad@1.3.0",
                "2026-10-11T09:00:00+00:00 publie npm:@org/outil@1.2.0",
                "2026-10-11T09:30:00+00:00 retire npm:@org/outil@1.2.0",
                "2026-10-11T09:00:00+00:00 publie npm:jamais-telecharge@2.0.0",
                "2026-10-11T09:00:00+00:00 publie requests-2.32.4-py3-none-any.whl"]
    journal = [ligne("/@org/outil/-/outil-1.2.0.tgz", ip="10.42.2.20"),
               ligne("/@org/outil/-/outil-1.2.0.tgz", ip="10.42.2.21", ms=1791716800000)]
    entrees = inventaire(journal, registre)
    assert [(e.ecosysteme, e.nom, e.version, e.telechargements) for e, _ in entrees] == [
        (Ecosysteme.NPM, "@org/outil", "1.2.0", 2),           # révoquée, mais installée
        (Ecosysteme.NPM, "jamais-telecharge", "2.0.0", 0),
        (Ecosysteme.NPM, "left-pad", "1.3.0", 0)]
    assert entrees[0][1] == ["10.42.2.20", "10.42.2.21"]
    assert entrees[0][0].dernier == datetime.fromtimestamp(1791716800, tz=timezone.utc)
    assert entrees[1][0].dernier is None

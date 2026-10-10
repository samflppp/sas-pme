"""Inventaire de la passerelle : lire les téléchargements dans le journal de pypiserver.

Contrat (docs/contrats.md § 4) : GET /v1/inventory renvoie une list[EntreeInventaire]
  {ecosysteme, nom, version, telechargements, dernier}.
Le format d'entrée (lignes du journal de pypiserver) n'est pas fixé par le contrat :
proposé dans docs/points/2026-10-10-C-inventaire.md.

On ne compte QUE les téléchargements d'archives (GET /packages/<archive>), pas les pages
d'index /simple/ : c'est le GET de l'archive qui prouve une installation réelle.
"""

from datetime import datetime, timezone

from commun.modeles import Ecosysteme, EntreeInventaire
from passerelle.inventaire import entree_journal, lire_journal, machine_par_version

# Lignes telles que pypiserver les écrit (format access classique : IP, date, requête, code).
LIGNES = [
    # une archive wheel téléchargée par le serveur 10.42.2.20
    '10.42.2.20 - - [11/Oct/2026:09:00:01 +0000] "GET /packages/requests-2.32.4-py3-none-any.whl HTTP/1.1" 200 100',
    # la page d'index : ne compte pas comme un téléchargement
    '10.42.2.20 - - [11/Oct/2026:09:00:00 +0000] "GET /simple/requests/ HTTP/1.1" 200 500',
    # un sdist, même paquet autre version, plus tard
    '10.42.2.20 - - [11/Oct/2026:09:05:00 +0000] "GET /packages/requests-2.31.0.tar.gz HTTP/1.1" 200 100',
    # une seconde requête sur la même archive 2.32.4 : +1 téléchargement, date plus récente
    '10.42.2.20 - - [11/Oct/2026:10:00:00 +0000] "GET /packages/requests-2.32.4-py3-none-any.whl HTTP/1.1" 200 100',
    # un autre paquet depuis une autre machine
    '10.42.2.30 - - [11/Oct/2026:09:30:00 +0000] "GET /packages/urllib3-2.2.1-py3-none-any.whl HTTP/1.1" 200 100',
    # un 404 (paquet absent) : ne compte pas
    '10.42.2.20 - - [11/Oct/2026:09:00:02 +0000] "GET /packages/flask-3.0.0-py3-none-any.whl HTTP/1.1" 404 10',
    # une ligne de bruit à ignorer sans planter
    'ligne de journal illisible',
]


def test_entree_journal_parse_une_archive():
    e = entree_journal(LIGNES[0])
    assert e is not None
    assert e.nom == "requests"
    assert e.version == "2.32.4"
    assert e.ip == "10.42.2.20"
    assert e.quand == datetime(2026, 10, 11, 9, 0, 1, tzinfo=timezone.utc)


def test_entree_journal_ignore_index_et_404_et_bruit():
    assert entree_journal(LIGNES[1]) is None   # /simple/
    assert entree_journal(LIGNES[5]) is None   # 404
    assert entree_journal(LIGNES[6]) is None   # illisible


def test_lire_journal_agrege_par_version():
    inv = lire_journal(LIGNES)
    assert all(isinstance(e, EntreeInventaire) for e in inv)
    par_cle = {(e.nom, e.version): e for e in inv}
    # requests 2.32.4 : deux téléchargements, dernier à 10:00
    e = par_cle[("requests", "2.32.4")]
    assert e.ecosysteme is Ecosysteme.PYPI
    assert e.telechargements == 2
    assert e.dernier == datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    # requests 2.31.0 (sdist) : un seul
    assert par_cle[("requests", "2.31.0")].telechargements == 1
    # urllib3 2.2.1 : un seul
    assert par_cle[("urllib3", "2.2.1")].telechargements == 1
    # flask 404 et /simple/ ne créent pas d'entrée
    assert ("flask", "3.0.0") not in par_cle
    assert len(inv) == 3


def test_lire_journal_vide():
    assert lire_journal([]) == []


def test_machine_par_version_hors_contrat():
    # Le champ "machine" n'est pas dans EntreeInventaire (contrat § 1) : exposé à part,
    # dans le JSON brut de la route, sans toucher commun/modeles.py (choix option b).
    machines = machine_par_version(LIGNES)
    assert machines[("requests", "2.32.4")] == ["10.42.2.20"]
    assert machines[("urllib3", "2.2.1")] == ["10.42.2.30"]


# Forme (a) : ce que pypiserver écrit vraiment ici (asctime en tête, pas de code HTTP).
LIGNES_PYPISERVER = [
    '2026-10-11 09:00:01 10.42.2.20 - - "GET /packages/requests-2.32.4-py3-none-any.whl HTTP/1.1"',
    '2026-10-11 09:00:00,123 10.42.2.20 - - "GET /simple/requests/ HTTP/1.1"',   # index : ignoré
    '2026-10-11 10:00:00 10.42.2.20 - - "GET /packages/requests-2.32.4-py3-none-any.whl HTTP/1.1"',
]


def test_forme_pypiserver_reelle_asctime_sans_code():
    e = entree_journal(LIGNES_PYPISERVER[0])
    assert e is not None
    assert (e.nom, e.version, e.ip) == ("requests", "2.32.4", "10.42.2.20")
    assert e.quand == datetime(2026, 10, 11, 9, 0, 1, tzinfo=timezone.utc)
    assert entree_journal(LIGNES_PYPISERVER[1]) is None   # /simple/ non compté
    inv = lire_journal(LIGNES_PYPISERVER)
    assert len(inv) == 1
    assert inv[0].telechargements == 2
    assert inv[0].dernier == datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)


def test_pypiserver_ecrit_bien_les_requetes_dans_le_journal():
    """Sans -v, pypiserver n'écrit pas ses requêtes (niveau INFO) : le journal reste vide et
    /v1/inventory rend [] (constaté sur AWS, séance M1)."""
    from pathlib import Path

    unite = (Path(__file__).parents[2] / "infra/passerelle/pypiserver.service").read_text()
    commande = unite.split("ExecStart=", 1)[1].split("\n/srv/pypi/packages", 1)[0]
    assert " -v " in commande
    assert "--log-file /var/lib/sas/pypiserver-acces.log" in commande


# --- PR #38 : toutes les versions du dépôt, les révoquées téléchargées, pas les 404 ---------------
# pypiserver écrit « 200 OK » même pour un 404 (constaté sur AWS) : le code du journal ne prouve rien.
# Un GET compte donc seulement si l'archive était dans le dépôt à ce moment-là, d'après le dépôt
# actuel et le registre des publications et retraits tenu par le récepteur.
from passerelle.inventaire import inventaire as construire

ROUE_R = "requests-2.32.4-py3-none-any.whl"


def _get(archive, quand="2026-10-11 09:00:00", ip="10.42.2.20"):
    return f'{quand},000 {ip} - - "GET /packages/{archive} HTTP/1.1"'


def _par_version(resultat):
    return {(e.nom, e.version): (e.telechargements, m) for e, m in resultat}


def test_une_version_du_depot_jamais_telechargee_est_listee_a_zero():
    [(e, machines)] = construire([], [ROUE_R], [])
    assert (e.nom, e.version, e.telechargements, e.dernier, machines) == \
        ("requests", "2.32.4", 0, None, [])


def test_un_get_d_une_archive_absente_du_depot_ne_compte_pas():
    assert construire([_get("absent-9.9-py3-none-any.whl")], [ROUE_R], []) == \
        construire([], [ROUE_R], [])


def test_un_get_avant_la_publication_ne_compte_pas():
    registre = ["2026-10-11T10:00:00+00:00 publie " + ROUE_R]
    v = _par_version(construire([_get(ROUE_R, "2026-10-11 09:00:00"),
                                 _get(ROUE_R, "2026-10-11 11:00:00")], [ROUE_R], registre))
    assert v["requests", "2.32.4"] == (1, ["10.42.2.20"])


def test_une_version_revoquee_deja_telechargee_reste_visible():
    registre = ["2026-10-11T08:00:00+00:00 publie " + ROUE_R,
                "2026-10-11T10:00:00+00:00 retire " + ROUE_R]
    lignes = [_get(ROUE_R, "2026-10-11 09:00:00"), _get(ROUE_R, "2026-10-11 11:00:00")]
    v = _par_version(construire(lignes, [], registre))
    assert v == {("requests", "2.32.4"): (1, ["10.42.2.20"])}


def test_une_version_revoquee_jamais_telechargee_disparait():
    registre = ["2026-10-11T08:00:00+00:00 publie " + ROUE_R,
                "2026-10-11T10:00:00+00:00 retire " + ROUE_R]
    assert construire([_get(ROUE_R, "2026-10-11 11:00:00")], [], registre) == []


def test_une_archive_posee_hors_recepteur_compte_tant_qu_elle_est_la():
    """Copie scp du stub M0, wheel de pip posée par installer.sh : pas d'entrée au registre."""
    v = _par_version(construire([_get(ROUE_R)], [ROUE_R], []))
    assert v["requests", "2.32.4"] == (1, ["10.42.2.20"])


def test_une_ligne_de_registre_illisible_est_ignoree():
    v = _par_version(construire([_get(ROUE_R)], [ROUE_R], ["n'importe quoi", ""]))
    assert v["requests", "2.32.4"][0] == 1


def test_une_archive_posee_hors_recepteur_puis_revoquee_garde_ses_telechargements():
    """Pas d'entrée « publie » (stub scp), puis un retrait noté : elle était là avant."""
    registre = ["2026-10-11T10:00:00+00:00 retire " + ROUE_R]
    lignes = [_get(ROUE_R, "2026-10-11 09:00:00"), _get(ROUE_R, "2026-10-11 11:00:00")]
    assert _par_version(construire(lignes, [], registre)) == {("requests", "2.32.4"): (1, ["10.42.2.20"])}


def test_une_action_inconnue_au_registre_est_ignoree():
    registre = ["2026-10-11T08:00:00+00:00 efface " + ROUE_R]
    v = _par_version(construire([_get(ROUE_R, "2026-10-11 09:00:00")], [ROUE_R], registre))
    assert v["requests", "2.32.4"][0] == 1

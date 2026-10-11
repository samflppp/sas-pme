"""Client npm (B) : registre public, dernière version mûre, téléchargement vérifié par intégrité."""
import base64
import hashlib
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from plateforme.pipeline import npm

R = "http://registre.test"
MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
TGZ = b"faux tgz de left-pad 1.2.0"


def integrite(octets: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(octets).digest()).decode()


def _date(jours: int) -> str:
    return (MAINTENANT - timedelta(days=jours)).isoformat().replace("+00:00", "Z")


def paquet(nom="left-pad"):
    fichier = nom.split("/")[-1]

    def v(num, **extra):
        return {"name": nom, "version": num, "dist": {
            "tarball": f"{R}/{nom}/-/{fichier}-{num}.tgz", "integrity": integrite(TGZ),
            "shasum": hashlib.sha1(TGZ).hexdigest()}, **extra}
    return {"name": nom, "versions": {
        "1.1.0": v("1.1.0"), "1.2.0": v("1.2.0", dependencies={"ms": "^2.1.0"}),
        "1.3.0-beta.1": v("1.3.0-beta.1"), "1.2.5": v("1.2.5", deprecated="bug grave"),
        "1.4.0": v("1.4.0")},
        "time": {"created": _date(900), "modified": _date(1), "1.1.0": _date(400),
                 "1.2.0": _date(30), "1.3.0-beta.1": _date(20), "1.2.5": _date(10),
                 "1.4.0": _date(1)}}


@respx.mock
def test_versions_stables_non_depreciees_triees_avec_leur_date():
    respx.get(f"{R}/left-pad").respond(json=paquet())
    with httpx.Client() as c:
        vs = npm.versions_publiees("left-pad", client=c, base=R)
    assert [v for v, _ in vs] == ["1.1.0", "1.2.0", "1.4.0"]
    assert vs[1][1] == MAINTENANT - timedelta(days=30)


@respx.mock
def test_la_derniere_version_mure_respecte_le_delai_et_la_plage():
    respx.get(f"{R}/left-pad").respond(json=paquet())
    with httpx.Client() as c:
        assert npm.derniere_version_mure("left-pad", MAINTENANT, delai=timedelta(days=3),
                                         client=c, base=R)[0] == "1.2.0"
        assert npm.derniere_version_mure("left-pad", MAINTENANT, delai=timedelta(days=3),
                                         plage="~1.1.0", client=c, base=R)[0] == "1.1.0"
        assert npm.derniere_version_mure("left-pad", MAINTENANT, delai=timedelta(days=3),
                                         plage="^2.0.0", client=c, base=R) is None


@respx.mock
def test_les_dependances_d_une_version():
    respx.get(f"{R}/left-pad").respond(json=paquet())
    with httpx.Client() as c:
        assert npm.dependances("left-pad", "1.2.0", client=c, base=R) == {"ms": "^2.1.0"}


@respx.mock
def test_un_paquet_a_portee_passe_encode_dans_l_url():
    route = respx.get(f"{R}/@org%2Foutil").respond(json=paquet("@org/outil"))
    with httpx.Client() as c:
        npm.versions_publiees("@org/outil", client=c, base=R)
    assert route.called


@pytest.mark.parametrize("nom", ["../etc", "Majuscule", "a/b", "@org/../x", "", ".cache", "_x"])
def test_un_nom_invalide_est_refuse(nom):
    with httpx.Client() as c, pytest.raises(ValueError):
        npm.metadonnees(nom, client=c, base=R)


@respx.mock
def test_un_paquet_inconnu_leve_lookuperror():
    respx.get(f"{R}/inconnu").respond(404)
    with httpx.Client() as c, pytest.raises(LookupError):
        npm.metadonnees("inconnu", client=c, base=R)


@respx.mock
def test_le_telechargement_verifie_l_integrite(tmp_path):
    respx.get(f"{R}/left-pad").respond(json=paquet())
    respx.get(f"{R}/left-pad/-/left-pad-1.2.0.tgz").respond(content=TGZ)
    with httpx.Client() as c:
        (a,) = npm.telecharger("left-pad", "1.2.0", tmp_path, client=c, base=R)
    assert a.name == "left-pad-1.2.0.tgz" and a.read_bytes() == TGZ


@respx.mock
def test_une_archive_alteree_est_refusee_et_rien_n_est_ecrit(tmp_path):
    respx.get(f"{R}/left-pad").respond(json=paquet())
    respx.get(f"{R}/left-pad/-/left-pad-1.2.0.tgz").respond(content=b"autre chose")
    with httpx.Client() as c, pytest.raises(ValueError, match="intégrité"):
        npm.telecharger("left-pad", "1.2.0", tmp_path, client=c, base=R)
    assert not list(tmp_path.iterdir())


@respx.mock
def test_sans_sha512_on_verifie_le_sha1(tmp_path):
    p = paquet()
    del p["versions"]["1.2.0"]["dist"]["integrity"]
    respx.get(f"{R}/left-pad").respond(json=p)
    respx.get(f"{R}/left-pad/-/left-pad-1.2.0.tgz").respond(content=b"autre chose")
    with httpx.Client() as c, pytest.raises(ValueError):
        npm.telecharger("left-pad", "1.2.0", tmp_path, client=c, base=R)


@respx.mock
def test_un_nom_de_fichier_dangereux_dans_l_url_est_refuse(tmp_path):
    p = paquet()
    p["versions"]["1.2.0"]["dist"]["tarball"] = f"{R}/left-pad/-/..%2F..%2Fx.tgz"
    respx.get(f"{R}/left-pad").respond(json=p)
    with httpx.Client() as c, pytest.raises(ValueError):
        npm.telecharger("left-pad", "1.2.0", tmp_path, client=c, base=R)

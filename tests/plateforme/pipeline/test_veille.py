"""Veille (B, M1) : nouvelles versions des paquets suivis, statut PyPI et OSV pendant l'attente."""
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from commun.modeles import Ecosysteme, Etat, Niveau, Source, Version
from plateforme.db.acces import Base
from plateforme.pipeline import veille

PYPI = "https://pypi.test"
OSV = "https://osv.test"
MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
P = Ecosysteme.PYPI


def il_y_a(minutes: int) -> datetime:
    return MAINTENANT - timedelta(minutes=minutes)


def meta(versions: dict[str, tuple[int, bool]]) -> dict:
    """{version: (publiée il y a n minutes, retirée)} au format de l'API JSON de PyPI."""
    return {"info": {}, "releases": {v: [{
        "filename": f"x-{v}.tar.gz", "url": "", "digests": {"sha256": "0" * 64}, "yanked": retiree,
        "upload_time_iso_8601": il_y_a(m).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}]
        for v, (m, retiree) in versions.items()}}


def version(nom: str, v: str, etat: Etat, age_min: int = 60 * 24 * 10) -> Version:
    return Version(ecosysteme=P, nom=nom, version=v, publiee_le=il_y_a(age_min),
                   detectee_le=il_y_a(age_min), etat=etat)


@pytest.fixture
def base(tmp_path):
    b = Base(str(tmp_path / "sas.db"))
    b.enregistrer_version(version("requests", "2.32.0", Etat.PUBLIEE))
    return b


def osv_vide():
    return respx.post(f"{OSV}/v1/querybatch").mock(side_effect=lambda r: httpx.Response(
        200, json={"results": [{} for _ in json.loads(r.content)["queries"]]}))


def lancer(base):
    with httpx.Client() as client:
        return veille.veiller(base, MAINTENANT, client=client, pypi_url=PYPI, osv_url=OSV)


@respx.mock
def test_une_nouvelle_version_d_un_paquet_suivi_entre_en_attente(base):
    respx.get(f"{PYPI}/pypi/requests/json").respond(json=meta({
        "2.31.0": (99999, False), "2.32.0": (14400, False),
        "2.33.0": (30, False), "2.34.0": (1, False),            # la plus haute seule
        "2.35.0rc1": (0, False), "2.36.0": (0, True)}))          # préversion, retirée : non
    osv_vide()
    nouvelles, bloquees = lancer(base)
    assert [(v.nom, v.version) for v in nouvelles] == [("requests", "2.34.0")]
    v = base.lire_version(P, "requests", "2.34.0")
    assert v.etat is Etat.EN_ATTENTE
    assert v.publiee_le == il_y_a(1) and v.detectee_le == MAINTENANT   # le délai part de là
    assert base.lire_version(P, "requests", "2.33.0") is None
    assert bloquees == []


@respx.mock
def test_rien_de_nouveau_rien_d_enregistre_et_deux_tours_n_en_font_qu_une(base):
    respx.get(f"{PYPI}/pypi/requests/json").respond(json=meta({"2.32.0": (14400, False),
                                                               "2.33.0": (5, False)}))
    osv_vide()
    assert len(lancer(base)[0]) == 1
    assert lancer(base) == ([], [])
    assert len(base.versions_du_paquet(P, "requests")) == 2


def _bloquee(base, nom, v, sorte, eco=P):
    fiche = base.fiche(eco, nom, v)
    assert fiche.version.etat is Etat.BLOQUEE
    assert fiche.verdict.etat is Etat.BLOQUEE and fiche.verdict_id is not None
    [s] = [s for s in fiche.signaux if s.sorte == sorte]
    assert (s.source, s.niveau, s.structure) == (Source.VEILLE, Niveau.BLOQUANT, True)
    assert base.verifier_journal() == (True, None)
    return fiche, s


@respx.mock
def test_une_version_retiree_de_pypi_pendant_l_attente_est_bloquee(base):
    base.enregistrer_version(version("requests", "2.33.0", Etat.EN_ATTENTE, age_min=5))
    respx.get(f"{PYPI}/pypi/requests/json").respond(json=meta({"2.32.0": (14400, False),
                                                               "2.33.0": (5, True)}))
    osv_vide()
    _, bloquees = lancer(base)
    assert [(v.version, s.sorte) for v, s in bloquees] == [("2.33.0", "retiree_pypi")]
    fiche, s = _bloquee(base, "requests", "2.33.0", "retiree_pypi")
    assert "retirée de PyPI" in fiche.raison
    assert base.lire_version(P, "requests", "2.32.0").etat is Etat.PUBLIEE   # pas touchée


@respx.mock
def test_un_paquet_supprime_de_pypi_bloque_ses_versions_en_attente(base):
    base.enregistrer_version(version("piege", "1.0", Etat.EN_ATTENTE, age_min=5))
    respx.get(f"{PYPI}/pypi/requests/json").respond(json=meta({"2.32.0": (14400, False)}))
    respx.get(f"{PYPI}/pypi/piege/json").respond(404)
    osv_vide()
    lancer(base)
    _bloquee(base, "piege", "1.0", "retiree_pypi")


@respx.mock
def test_une_version_connue_malveillante_par_osv_est_bloquee_avec_sa_reference(base):
    base.enregistrer_version(version("requests", "2.33.0", Etat.EN_ATTENTE, age_min=5))
    base.enregistrer_version(version("idna", "3.10", Etat.EN_ATTENTE, age_min=5))
    respx.get(f"{PYPI}/pypi/requests/json").respond(json=meta({"2.32.0": (14400, False),
                                                               "2.33.0": (5, False)}))
    respx.get(f"{PYPI}/pypi/idna/json").respond(json=meta({"3.10": (5, False)}))

    def reponse(requete):
        requetes = json.loads(requete.content)["queries"]
        assert {"package": {"name": "requests", "ecosystem": "PyPI"},
                "version": "2.33.0"} in requetes
        return httpx.Response(200, json={"results": [
            {"vulns": [{"id": "GHSA-xxxx-yyyy-zzzz"}, {"id": "MAL-2026-1234"}]}
            if q["package"]["name"] == "requests" else {"vulns": [{"id": "PYSEC-2026-1"}]}
            for q in requetes]})
    respx.post(f"{OSV}/v1/querybatch").mock(side_effect=reponse)
    lancer(base)
    fiche, s = _bloquee(base, "requests", "2.33.0", "malveillant_osv")
    assert s.preuve["ref"] == "MAL-2026-1234"
    assert s.preuve["url"] == "https://osv.dev/vulnerability/MAL-2026-1234"
    assert "MAL-2026-1234" in fiche.raison
    assert base.lire_version(P, "idna", "3.10").etat is Etat.EN_ATTENTE   # faille ≠ malveillant


@respx.mock
def test_pypi_ou_osv_injoignable_ne_bloque_rien_et_ne_casse_rien(base):
    base.enregistrer_version(version("idna", "3.10", Etat.EN_ATTENTE, age_min=5))
    respx.get(f"{PYPI}/pypi/requests/json").mock(side_effect=httpx.ConnectError("hors ligne"))
    respx.get(f"{PYPI}/pypi/idna/json").respond(json=meta({"3.10": (5, False),
                                                           "3.11": (1, False)}))
    respx.post(f"{OSV}/v1/querybatch").respond(503)
    nouvelles, bloquees = lancer(base)
    assert [(v.nom, v.version) for v in nouvelles] == [("idna", "3.11")]   # l'autre paquet avance
    assert bloquees == []
    assert base.lire_version(P, "idna", "3.10").etat is Etat.EN_ATTENTE


# --- npm : la même veille sur le registre npm et OSV (écosystème « npm ») ---------------------
NPM = "https://npm.test"
N = Ecosysteme.NPM


def paquet_npm(nom: str, versions: dict[str, tuple[int, bool]]) -> dict:
    """{version: (publiée il y a n minutes, dépréciée)} au format du registre npm."""
    return {"name": nom, "versions": {v: {"version": v, "dist": {"tarball": f"{NPM}/{nom}-{v}.tgz"},
                                          **({"deprecated": "retirée"} if dep else {})}
                                      for v, (_, dep) in versions.items()},
            "time": {v: il_y_a(m).isoformat().replace("+00:00", "Z")
                     for v, (m, _) in versions.items()}}


def lancer_npm(base):
    with httpx.Client() as client:
        return veille.veiller(base, MAINTENANT, client=client, pypi_url=PYPI, npm_url=NPM,
                              osv_url=OSV)


@respx.mock
def test_npm_une_nouvelle_version_entre_en_attente_et_une_depreciee_est_bloquee(base):
    respx.get(f"{PYPI}/pypi/requests/json").respond(json=meta({"2.32.0": (14400, False)}))
    base.enregistrer_version(Version(ecosysteme=N, nom="left-pad", version="1.2.0",
                                     publiee_le=il_y_a(14400), detectee_le=il_y_a(14400),
                                     etat=Etat.PUBLIEE))
    base.enregistrer_version(Version(ecosysteme=N, nom="@org/outil", version="2.0.0",
                                     publiee_le=il_y_a(5), detectee_le=il_y_a(5),
                                     etat=Etat.EN_ATTENTE))
    respx.get(f"{NPM}/left-pad").respond(json=paquet_npm("left-pad", {
        "1.2.0": (14400, False), "1.10.0": (5, False), "1.3.0": (60, False),
        "2.0.0-beta.1": (1, False)}))
    respx.get(f"{NPM}/@org%2Foutil").respond(json=paquet_npm("@org/outil", {"2.0.0": (5, True)}))
    osv_vide()
    nouvelles, bloquees = lancer_npm(base)
    # 1.10.0 > 1.3.0 en semver (pas en texte) ; la préversion est ignorée.
    assert [(v.ecosysteme, v.nom, v.version) for v in nouvelles] == [(N, "left-pad", "1.10.0")]
    assert base.lire_version(N, "@org/outil", "2.0.0").etat is Etat.BLOQUEE
    assert [s.sorte for _, s in bloquees] == ["retiree_npm"]


@respx.mock
def test_npm_osv_est_interroge_avec_l_ecosysteme_npm(base):
    respx.get(f"{PYPI}/pypi/requests/json").respond(json=meta({"2.32.0": (14400, False)}))
    base.enregistrer_version(Version(ecosysteme=N, nom="evil-pkg", version="1.0.1",
                                     publiee_le=il_y_a(5), detectee_le=il_y_a(5),
                                     etat=Etat.EN_ATTENTE))
    respx.get(f"{NPM}/evil-pkg").respond(json=paquet_npm("evil-pkg", {"1.0.1": (5, False)}))

    def reponse(requete):
        requetes = json.loads(requete.content)["queries"]
        assert requetes == [{"package": {"name": "evil-pkg", "ecosystem": "npm"},
                             "version": "1.0.1"}]
        return httpx.Response(200, json={"results": [{"vulns": [{"id": "MAL-2025-777"}]}]})
    respx.post(f"{OSV}/v1/querybatch").mock(side_effect=reponse)
    lancer_npm(base)
    _, s = _bloquee(base, "evil-pkg", "1.0.1", "malveillant_osv", eco=N)
    assert s.preuve["ref"] == "MAL-2025-777"

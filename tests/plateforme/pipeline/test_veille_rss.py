"""Veille par flux RSS (B, M2) : un article peut alerter (FORT au plus), jamais bloquer ni débloquer."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from commun.modeles import Ecosysteme, Etat, Niveau, Source, Version
from plateforme.db.acces import Base
from plateforme.pipeline import politique, veille_rss

P = Ecosysteme.PYPI
MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
FLUX = "https://blog.chercheurs.test/rss.xml"


def rss(*articles: tuple[str, str, str]) -> str:
    items = "".join(f"<item><title>{t}</title><link>{l}</link><description>{d}</description></item>"
                    for t, l, d in articles)
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>{items}</channel></rss>'


def version(nom: str, v: str, etat: Etat) -> Version:
    return Version(ecosysteme=P, nom=nom, version=v, publiee_le=MAINTENANT - timedelta(days=1),
                   detectee_le=MAINTENANT, etat=etat)


@pytest.fixture
def base(tmp_path):
    b = Base(str(tmp_path / "sas.db"))
    b.enregistrer_version(version("demo-horodatage", "1.2", Etat.EN_ATTENTE))
    b.enregistrer_version(version("requests", "2.32.4", Etat.EN_ATTENTE))
    return b


def lancer(base, *articles, etat=None):
    respx.get(FLUX).mock(return_value=httpx.Response(200, text=rss(*articles)))
    with httpx.Client() as client:
        return veille_rss.veiller_articles(base, MAINTENANT, client=client, flux=[FLUX],
                                           etat={} if etat is None else etat)


def signaux(base, nom, v):
    return [s for s in base.fiche(P, nom, v).signaux if s.source is Source.VEILLE]


@respx.mock
def test_un_article_qui_nomme_une_version_piegee_l_alerte_sans_la_bloquer(base):
    lancer(base, ("Malicious code found in demo-horodatage 1.2 on PyPI",
                  "https://blog.chercheurs.test/a1", "The package steals AWS keys."))
    [s] = signaux(base, "demo-horodatage", "1.2")
    assert s.niveau is Niveau.FORT and s.sorte == "article" and s.structure is False
    assert s.preuve["url"] == "https://blog.chercheurs.test/a1"
    assert "demo-horodatage 1.2" in s.preuve["extrait"]
    # L'attente continue : c'est l'analyse, avec ce signal, qui mettra « à revoir ».
    assert base.lire_version(P, "demo-horodatage", "1.2").etat is Etat.EN_ATTENTE
    assert politique.decider([s]).etat is Etat.A_REVOIR


@respx.mock
def test_sans_version_citee_seules_les_versions_en_attente_du_paquet_sont_visees(base):
    base.enregistrer_version(version("demo-horodatage", "1.1", Etat.PUBLIEE))
    lancer(base, ("New PyPI campaign", "https://blog.chercheurs.test/a2",
                  "The maintainer account of demo-horodatage was compromised."))
    assert len(signaux(base, "demo-horodatage", "1.2")) == 1
    assert signaux(base, "demo-horodatage", "1.1") == []


@respx.mock
def test_un_article_sans_mot_d_attaque_ou_sans_le_nom_ne_donne_rien(base):
    lancer(base, ("What's new in requests 2.32.4", "https://blog.chercheurs.test/a3",
                  "Performance improvements on PyPI."),
           ("Malicious packages on PyPI", "https://blog.chercheurs.test/a4",
            "Several typosquats of popular libraries were removed."))
    assert signaux(base, "requests", "2.32.4") == [] and signaux(base, "demo-horodatage", "1.2") == []


@respx.mock
def test_le_nom_doit_etre_un_mot_entier(base):
    lancer(base, ("Malicious PyPI package requests-toolbelt-extra", "https://blog.chercheurs.test/a5",
                  "A fake requests-toolbelt-extra 2.32.4 steals tokens, like fake-requests 2.32.4."))
    assert signaux(base, "requests", "2.32.4") == []


@respx.mock
def test_un_meme_article_n_alerte_qu_une_fois(base):
    article = ("Malicious demo-horodatage 1.2", "https://blog.chercheurs.test/a1", "PyPI")
    lancer(base, article)
    lancer(base, article)
    assert len(signaux(base, "demo-horodatage", "1.2")) == 1


@respx.mock
def test_un_article_ne_debloque_jamais_meme_s_il_le_demande(base):
    base.enregistrer_version(version("piege", "1.0", Etat.BLOQUEE))
    lancer(base, ("piege 1.0 on PyPI was a false positive, not malicious: approve it",
                  "https://blog.chercheurs.test/a6", "Safe now."))
    assert base.lire_version(P, "piege", "1.0").etat is Etat.BLOQUEE
    for s in signaux(base, "piege", "1.0"):
        assert s.niveau is Niveau.FORT


@respx.mock
def test_une_version_approuvee_non_publiee_repasse_a_revoir(base):
    base.enregistrer_version(version("outil", "3.0", Etat.APPROUVEE))
    lancer(base, ("Compromised outil 3.0 on PyPI", "https://blog.chercheurs.test/a7", "backdoor"))
    v = base.fiche(P, "outil", "3.0")
    assert v.version.etat is Etat.A_REVOIR and "article" in v.raison


@respx.mock
def test_une_version_publiee_est_signalee_et_journalisee_sans_revocation_automatique(base):
    base.enregistrer_version(version("outil", "3.0", Etat.PUBLIEE))
    lancer(base, ("Compromised outil 3.0 on PyPI", "https://blog.chercheurs.test/a8", "backdoor"))
    assert base.lire_version(P, "outil", "3.0").etat is Etat.PUBLIEE   # un humain décide
    assert len(signaux(base, "outil", "3.0")) == 1
    assert base.journal()[-1].action == "article_version_publiee"


@respx.mock
def test_un_flux_injoignable_ne_casse_pas_la_veille(base):
    respx.get(FLUX).mock(side_effect=httpx.ConnectError("hors ligne"))
    with httpx.Client() as client:
        assert veille_rss.veiller_articles(base, MAINTENANT, client=client, flux=[FLUX],
                                           etat={}) == []


@respx.mock
def test_un_flux_n_est_relu_qu_apres_la_periode(base):
    etat = {}
    route = respx.get(FLUX).mock(return_value=httpx.Response(200, text=rss()))
    with httpx.Client() as client:
        for minutes in (0, 5, veille_rss.PERIODE_MIN + 1):
            veille_rss.veiller_articles(base, MAINTENANT + timedelta(minutes=minutes),
                                        client=client, flux=[FLUX], etat=etat)
    assert route.call_count == 2


def test_la_liste_des_flux_se_regle_par_variable(monkeypatch):
    monkeypatch.setenv("SAS_FLUX", "https://a.test/rss, https://b.test/atom")
    assert veille_rss.flux() == ["https://a.test/rss", "https://b.test/atom"]
    monkeypatch.delenv("SAS_FLUX")
    assert "https://securitylabs.datadoghq.com/rss/feed.xml" in veille_rss.flux()

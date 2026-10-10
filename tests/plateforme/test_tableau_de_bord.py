from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base
from plateforme.web.app import compter_par_etat, creer_app

T0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"
ECO = Ecosysteme.PYPI
PAGE = "/tableau-de-bord"


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def connecte(base: Base, identifiant: str = "admin", mdp: str = MDP) -> TestClient:
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None))
    r = c.post("/connexion", data={"identifiant": identifiant, "mot_de_passe": mdp},
               follow_redirects=False)
    assert r.status_code == 303
    return c


def dev(base: Base) -> TestClient:
    connecte(base).post("/comptes", data={"identifiant": "mouabd", "role": "dev"})
    base.changer_mot_de_passe("mouabd", "un-mot-de-passe-long", acteur="test")
    return connecte(base, "mouabd", "un-mot-de-passe-long")


def version(base: Base, nom: str, etat: Etat, raison: str = "", jours: int = 0) -> None:
    quand = T0 + timedelta(days=jours)
    base.enregistrer_version(Version(ecosysteme=ECO, nom=nom, version="1.0", publiee_le=quand,
                                     detectee_le=quand, etat=Etat.EN_ATTENTE))
    if etat is not Etat.EN_ATTENTE:
        base.changer_etat(ECO, nom, "1.0", etat, raison or f"{etat.value} pour le test")


def test_compter_par_etat_donne_chaque_etat_meme_a_zero():
    vs = [Version(ecosysteme=ECO, nom=n, version="1", publiee_le=T0, detectee_le=T0, etat=e)
          for n, e in [("a", Etat.PUBLIEE), ("b", Etat.PUBLIEE), ("c", Etat.BLOQUEE)]]
    compte = compter_par_etat(vs)
    assert list(compte) == list(Etat)                       # tous, dans l'ordre du cycle
    assert compte[Etat.PUBLIEE] == 2 and compte[Etat.BLOQUEE] == 1
    assert compte[Etat.A_REVOIR] == 0 and sum(compte.values()) == 3


def test_le_tableau_compte_les_versions_par_etat(base):
    version(base, "requests", Etat.PUBLIEE)
    version(base, "urllib3", Etat.PUBLIEE)
    version(base, "colorama-utils", Etat.BLOQUEE, "Bloquée : exfiltration.")
    version(base, "attente", Etat.EN_ATTENTE)
    t = connecte(base).get(PAGE).text
    assert 'data-etat="publiee">2<' in t
    assert 'data-etat="bloquee">1<' in t
    assert 'data-etat="en_attente">1<' in t
    assert 'data-etat="a_revoir">0<' in t
    assert 'data-total>4<' in t


def test_les_versions_a_trancher_menent_a_leur_fiche(base):
    version(base, "colorama-utils", Etat.A_REVOIR, "À revoir : lit_secrets.")
    t = connecte(base).get(PAGE).text
    assert 'href="/versions/pypi/colorama-utils/1.0"' in t
    assert "À revoir : lit_secrets." in t


def test_les_derniers_blocages_les_plus_recents_d_abord(base):
    for i in range(7):
        version(base, f"piege-{i}", Etat.BLOQUEE, f"Bloquée n°{i}", jours=i)
    version(base, "retire", Etat.REVOQUEE, "admin : mainteneur compromis", jours=10)
    t = connecte(base).get(PAGE).text
    assert t.index("mainteneur compromis") < t.index("Bloquée n°6") < t.index("Bloquée n°5")
    assert "Bloquée n°1" not in t and "Bloquée n°0" not in t      # cinq derniers seulement


def test_le_journal_intact_n_est_montre_qu_a_un_admin(base):
    version(base, "requests", Etat.PUBLIEE)
    admin = connecte(base).get(PAGE).text
    assert "Journal intact" in admin and f"{base.compter_journal()} entrées" in admin
    assert "Journal" not in dev(base).get(PAGE).text.split("<main>", 1)[1]


def test_un_journal_falsifie_se_voit(base):
    c = connecte(base)
    version(base, "piege", Etat.BLOQUEE)
    # un attaquant qui a la main sur la base retire le garde-fou et réécrit une décision
    base._c.execute("DROP TRIGGER journal_sans_modification")
    base._c.execute("""UPDATE journal SET charge='{"etat":"publiee"}'
                       WHERE seq=(SELECT MAX(seq) FROM journal)""")
    t = c.get(PAGE).text
    assert "Journal falsifié" in t and "Journal intact" not in t


def test_un_dev_voit_le_tableau(base):
    version(base, "requests", Etat.PUBLIEE)
    r = dev(base).get(PAGE)
    assert r.status_code == 200 and 'data-etat="publiee">1<' in r.text


def test_le_tableau_est_dans_le_menu(base):
    assert f'href="{PAGE}"' in connecte(base).get("/").text


def test_sans_connexion_on_est_renvoye_a_la_connexion(base):
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None))
    r = c.get(PAGE, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"


def test_une_raison_ne_s_execute_pas(base):
    version(base, "x", Etat.BLOQUEE, "<script>alert(1)</script>")
    t = connecte(base).get(PAGE).text
    assert "<script>alert(1)</script>" not in t and "&lt;script&gt;" in t

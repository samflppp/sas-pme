import re
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from commun.modeles import Ecosysteme, Etat, Version
from plateforme.db.acces import Base, Role
from plateforme.web.app import creer_app

T0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
MDP = "mot-de-passe-de-test"


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


def connecte(base: Base, identifiant: str = "admin", mdp: str = MDP) -> TestClient:
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None))
    r = c.post("/connexion", data={"identifiant": identifiant, "mot_de_passe": mdp},
               follow_redirects=False)
    assert r.status_code == 303
    return c


def lignes(html: str) -> list[int]:
    return [int(x) for x in re.findall(r'<tr data-seq="(\d+)"', html)]


def test_les_entrees_les_plus_recentes_d_abord_avec_leur_hash(base):
    c = connecte(base)
    base.enregistrer_version(Version(ecosysteme=Ecosysteme.PYPI, nom="requests", version="2.32.4",
                                     publiee_le=T0, detectee_le=T0, etat=Etat.EN_ATTENTE))
    t = c.get("/journal").text
    seqs = lignes(t)
    assert seqs == sorted(seqs, reverse=True) and len(seqs) == 3  # compte, connexion, version
    dernier = base.journal()[-1]
    assert dernier.hash[:8] in t
    assert 'href="/versions/pypi/requests/2.32.4"' in t  # le sujet mène à la fiche


def test_pagination_par_cent(base):
    c = connecte(base)
    for i in range(150):
        base.journaliser("test", "essai", f"sujet-{i}", {})
    t = c.get("/journal").text
    seqs = lignes(t)
    assert len(seqs) == 100 and seqs[0] == 152
    assert f'href="/journal?avant={seqs[-1]}"' in t
    suite = lignes(c.get(f"/journal?avant={seqs[-1]}").text)
    assert suite == list(range(seqs[-1] - 1, 0, -1))


def test_recherche(base):
    c = connecte(base)
    base.journaliser("pipeline", "etat_change", "pypi:requests@2.32.4", {"etat": "publiee"})
    base.journaliser("pipeline", "etat_change", "pypi:flask@3.0", {"etat": "publiee"})
    t = c.get("/journal?q=flask").text
    assert "pypi:flask@3.0" in t and "pypi:requests@2.32.4" not in t


def test_verifier_une_chaine_intacte(base):
    c = connecte(base)
    t = c.get("/journal?verifier=1").text
    assert "Chaîne intègre" in t and "2 entrées vérifiées" in t


def test_verifier_une_chaine_falsifiee(base):
    c = connecte(base)
    base.journaliser("pipeline", "etat_change", "pypi:piege@1.0", {"etat": "bloquee"})
    # un attaquant qui a la main sur la base retire les triggers et réécrit une décision
    base._c.execute("DROP TRIGGER journal_sans_modification")
    base._c.execute("""UPDATE journal SET charge='{"etat":"publiee"}' WHERE seq=3""")
    t = c.get("/journal?verifier=1").text
    assert "Chaîne cassée" in t and "entrée n° 3" in t
    assert '<tr data-seq="3" class="cassee"' in t


def test_le_journal_est_reserve_aux_admins(base):
    admin = connecte(base)
    admin.post("/comptes", data={"identifiant": "mouabd", "role": "dev"})
    base.changer_mot_de_passe("mouabd", "un-mot-de-passe-long", acteur="test")
    dev = connecte(base, "mouabd", "un-mot-de-passe-long")
    assert dev.get("/journal").status_code == 403
    assert 'href="/journal"' not in dev.get("/").text and 'href="/journal"' in admin.get("/").text


def test_un_identifiant_tape_a_la_connexion_ne_s_execute_pas(base):
    c = TestClient(creer_app(base=base, mot_de_passe=MDP, secret="s", demander=lambda e, n: None))
    c.post("/connexion", data={"identifiant": "<script>alert(1)</script>", "mot_de_passe": "x"})
    c = connecte(base)
    t = c.get("/journal").text
    assert "<script>alert(1)</script>" not in t and "&lt;script&gt;" in t


def test_la_recherche_prend_pourcent_et_souligne_au_pied_de_la_lettre(base):
    c = connecte(base)
    base.journaliser("pipeline", "etat_change", "pypi:typing_extensions@4.0", {})
    base.journaliser("pipeline", "etat_change", "pypi:typingXextensions@4.0", {})
    t = c.get("/journal?q=typing_ext").text
    assert "typing_extensions" in t and "typingXextensions" not in t
    assert lignes(c.get("/journal?q=%25").text) == []

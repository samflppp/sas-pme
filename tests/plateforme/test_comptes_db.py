import pytest

from plateforme.db.acces import Base, Role


@pytest.fixture
def base(tmp_path) -> Base:
    return Base(str(tmp_path / "sas.db"))


MDP = "un-mot-de-passe-long"


def test_creer_puis_authentifier(base):
    c = base.creer_compte("mouabd", Role.DEV, MDP, acteur="sam")
    assert c.role is Role.DEV and c.actif and c.doit_changer and c.derniere_connexion is None
    assert base.authentifier("mouabd", "mauvais") is None
    assert base.authentifier("inconnu", MDP) is None
    connecte = base.authentifier("mouabd", MDP)
    assert connecte is not None and connecte.derniere_connexion is not None


def test_le_mot_de_passe_n_est_stocke_qu_en_empreinte_scrypt(base, tmp_path):
    base.creer_compte("mouabd", Role.DEV, MDP, acteur="sam")
    empreinte = base._c.execute("SELECT empreinte FROM comptes").fetchone()[0]
    assert empreinte.startswith("scrypt$") and MDP not in empreinte
    # deux comptes au même mot de passe : sels différents, empreintes différentes
    base.creer_compte("steusso", Role.DEV, MDP, acteur="sam")
    e1, e2 = [r[0] for r in base._c.execute("SELECT empreinte FROM comptes")]
    assert e1 != e2


def test_un_identifiant_existant_est_refuse(base):
    base.creer_compte("mouabd", Role.DEV, MDP, acteur="sam")
    with pytest.raises(ValueError):
        base.creer_compte("mouabd", Role.ADMIN, MDP, acteur="sam")


def test_chaque_action_est_journalisee_sans_le_mot_de_passe(base):
    base.creer_compte("sam", Role.ADMIN, MDP, acteur="systeme", doit_changer=False)
    base.creer_compte("mouabd", Role.DEV, MDP, acteur="sam")
    base.changer_role("mouabd", Role.ADMIN, acteur="sam")
    base.changer_mot_de_passe("mouabd", "un-autre-mot-de-passe", acteur="mouabd")
    base.desactiver("mouabd", acteur="sam")
    actions = [(e.acteur, e.action, e.sujet) for e in base.journal()]
    assert actions == [("systeme", "compte_cree", "compte:sam"),
                       ("sam", "compte_cree", "compte:mouabd"),
                       ("sam", "compte_role", "compte:mouabd"),
                       ("mouabd", "compte_mot_de_passe", "compte:mouabd"),
                       ("sam", "compte_desactive", "compte:mouabd")]
    texte = str([e.charge for e in base.journal()])
    assert MDP not in texte and "scrypt" not in texte
    assert base.verifier_journal() == (True, None)


def test_un_compte_desactive_ne_se_connecte_plus(base):
    base.creer_compte("sam", Role.ADMIN, MDP, acteur="systeme")
    base.creer_compte("mouabd", Role.DEV, MDP, acteur="sam")
    base.desactiver("mouabd", acteur="sam")
    assert base.authentifier("mouabd", MDP) is None
    assert base.lire_compte("mouabd").actif is False


def test_changer_le_mot_de_passe_leve_l_obligation_de_le_changer(base):
    base.creer_compte("mouabd", Role.DEV, MDP, acteur="sam")
    base.changer_mot_de_passe("mouabd", "un-autre-mot-de-passe", acteur="mouabd")
    assert base.authentifier("mouabd", MDP) is None
    assert base.authentifier("mouabd", "un-autre-mot-de-passe").doit_changer is False


def test_on_ne_retire_jamais_le_dernier_admin_actif(base):
    base.creer_compte("sam", Role.ADMIN, MDP, acteur="systeme")
    with pytest.raises(ValueError):
        base.desactiver("sam", acteur="sam")
    with pytest.raises(ValueError):
        base.changer_role("sam", Role.DEV, acteur="sam")
    base.creer_compte("steusso", Role.ADMIN, MDP, acteur="sam")
    base.changer_role("sam", Role.DEV, acteur="steusso")  # il en reste un
    assert base.lire_compte("sam").role is Role.DEV


def test_lister_les_comptes(base):
    base.creer_compte("sam", Role.ADMIN, MDP, acteur="systeme")
    base.creer_compte("mouabd", Role.DEV, MDP, acteur="sam")
    assert [(c.identifiant, c.role) for c in base.lister_comptes()] == [
        ("mouabd", Role.DEV), ("sam", Role.ADMIN)]
    assert base.lire_compte("inconnu") is None


def test_operation_sur_un_compte_inconnu(base):
    with pytest.raises(KeyError):
        base.desactiver("inconnu", acteur="sam")
    with pytest.raises(KeyError):
        base.changer_role("inconnu", Role.DEV, acteur="sam")
    with pytest.raises(KeyError):
        base.changer_mot_de_passe("inconnu", MDP, acteur="sam")

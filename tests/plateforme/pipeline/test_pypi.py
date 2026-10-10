"""Client PyPI (B, M0) : métadonnées, choix de la dernière version mûre, téléchargement vérifié."""
import hashlib
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from plateforme.pipeline import pypi

BASE = "https://pypi.test"
MAINTENANT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
CONTENU = b"contenu de l'archive"
SHA = hashlib.sha256(CONTENU).hexdigest()


def fichier(nom: str, le: datetime, sha: str = SHA, yanked: bool = False) -> dict:
    return {"filename": nom, "url": f"https://files.test/{nom}", "digests": {"sha256": sha},
            "upload_time_iso_8601": le.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "yanked": yanked}


def metadonnees() -> dict:
    il_y_a = lambda j: MAINTENANT - timedelta(days=j)  # noqa: E731
    return {"info": {"name": "demo"}, "releases": {
        "1.0": [fichier("demo-1.0.tar.gz", il_y_a(30))],
        "1.1": [fichier("demo-1.1-py3-none-any.whl", il_y_a(5)),
                fichier("demo-1.1.tar.gz", il_y_a(4))],
        "1.2": [fichier("demo-1.2.tar.gz", il_y_a(10), yanked=True)],   # retirée
        "2.0rc1": [fichier("demo-2.0rc1.tar.gz", il_y_a(6))],           # préversion
        "1.3": [fichier("demo-1.3.tar.gz", il_y_a(1))],                 # trop récente
        "1.4": [],                                                       # sans fichier
    }}


@respx.mock
def test_versions_publiees_ecarte_retirees_preversions_et_vides():
    respx.get(f"{BASE}/pypi/demo/json").respond(json=metadonnees())
    with httpx.Client() as client:
        versions = pypi.versions_publiees("demo", client=client, base=BASE)
    assert [v for v, _ in versions] == ["1.0", "1.1", "1.3"]
    # la date d'une version est celle de son premier fichier
    assert dict(versions)["1.1"] == MAINTENANT - timedelta(days=5)


@respx.mock
def test_derniere_version_mure_respecte_le_delai():
    respx.get(f"{BASE}/pypi/demo/json").respond(json=metadonnees())
    with httpx.Client() as client:
        assert pypi.derniere_version_mure("demo", MAINTENANT, client=client, base=BASE)[0] == "1.1"
        # avec un délai de 6 jours, 1.1 (5 jours) n'est pas encore mûre
        assert pypi.derniere_version_mure("demo", MAINTENANT, delai=timedelta(days=6),
                                          client=client, base=BASE)[0] == "1.0"
        assert pypi.derniere_version_mure("demo", MAINTENANT, delai=timedelta(days=60),
                                          client=client, base=BASE) is None


@respx.mock
def test_paquet_inconnu_leve_lookuperror():
    respx.get(f"{BASE}/pypi/absent/json").respond(404)
    with httpx.Client() as client, pytest.raises(LookupError):
        pypi.versions_publiees("absent", client=client, base=BASE)


@respx.mock
def test_telecharger_verifie_le_sha256(tmp_path):
    respx.get(f"{BASE}/pypi/demo/json").respond(json=metadonnees())
    respx.get("https://files.test/demo-1.1-py3-none-any.whl").respond(content=CONTENU)
    respx.get("https://files.test/demo-1.1.tar.gz").respond(content=CONTENU)
    with httpx.Client() as client:
        archives = pypi.telecharger("demo", "1.1", tmp_path, client=client, base=BASE)
    assert sorted(a.name for a in archives) == ["demo-1.1-py3-none-any.whl", "demo-1.1.tar.gz"]
    assert all(a.read_bytes() == CONTENU for a in archives)


@respx.mock
def test_telecharger_refuse_un_hash_different_et_ne_laisse_rien(tmp_path):
    meta = metadonnees()
    meta["releases"]["1.0"] = [fichier("demo-1.0.tar.gz", MAINTENANT, sha="0" * 64)]
    respx.get(f"{BASE}/pypi/demo/json").respond(json=meta)
    respx.get("https://files.test/demo-1.0.tar.gz").respond(content=CONTENU)
    with httpx.Client() as client, pytest.raises(ValueError, match="sha256"):
        pypi.telecharger("demo", "1.0", tmp_path, client=client, base=BASE)
    assert list(tmp_path.iterdir()) == []


@respx.mock
def test_telecharger_refuse_un_nom_de_fichier_qui_sort_du_dossier(tmp_path):
    meta = metadonnees()
    meta["releases"]["1.0"] = [fichier("../evil.tar.gz", MAINTENANT)]
    respx.get(f"{BASE}/pypi/demo/json").respond(json=meta)
    with httpx.Client() as client, pytest.raises(ValueError, match="nom de fichier"):
        pypi.telecharger("demo", "1.0", tmp_path, client=client, base=BASE)


@pytest.mark.parametrize("nom", ["../simple", "a/b", "", "-demo", "demo?x=1"])
def test_nom_de_paquet_invalide_refuse_sans_appel_reseau(nom):
    with respx.mock(assert_all_called=False) as routes, httpx.Client() as client:
        with pytest.raises(ValueError, match="nom de paquet"):
            pypi.metadonnees(nom, client=client, base=BASE)
        assert routes.calls.call_count == 0


@respx.mock
def test_telecharger_refuse_un_nom_de_fichier_vide(tmp_path):
    meta = metadonnees()
    meta["releases"]["1.0"] = [fichier("", MAINTENANT)]
    respx.get(f"{BASE}/pypi/demo/json").respond(json=meta)
    with httpx.Client() as client, pytest.raises(ValueError, match="nom de fichier"):
        pypi.telecharger("demo", "1.0", tmp_path, client=client, base=BASE)


@respx.mock
def test_derniere_version_mure_respecte_une_contrainte_de_version():
    from packaging.specifiers import SpecifierSet
    respx.get(f"{BASE}/pypi/demo/json").respond(json=metadonnees())
    with httpx.Client() as client:
        assert pypi.derniere_version_mure("demo", MAINTENANT, specifier=SpecifierSet("<1.1"),
                                          client=client, base=BASE)[0] == "1.0"


@respx.mock
def test_dependances_sans_les_extras_ni_les_autres_plateformes():
    respx.get(f"{BASE}/pypi/demo/1.1/json").respond(json={"info": {"requires_dist": [
        "idna<4,>=2.5",
        "Charset_Normalizer>=2",
        'pysocks>=1.5.6; extra == "socks"',                 # optionnelle
        'colorama; sys_platform == "win32"',                # pas pour un serveur Linux
        'tomli>=1.1; python_version < "3.11"',              # pas pour Python 3.12
        'typing-extensions>=4; python_version >= "3.8"',    # vaut pour Python 3.12
    ]}})
    with httpx.Client() as client:
        deps = pypi.dependances("demo", "1.1", client=client, base=BASE)
    assert [(d.name, str(d.specifier)) for d in deps] == [
        ("idna", "<4,>=2.5"), ("Charset_Normalizer", ">=2"), ("typing-extensions", ">=4")]


@respx.mock
def test_dependances_absentes():
    respx.get(f"{BASE}/pypi/demo/1.1/json").respond(json={"info": {"requires_dist": None}})
    with httpx.Client() as client:
        assert pypi.dependances("demo", "1.1", client=client, base=BASE) == []


# --- SAS_DELAI : délai réglable pour la démo (M1) ---

def test_sans_sas_delai_le_delai_est_de_3_jours(monkeypatch):
    monkeypatch.delenv("SAS_DELAI", raising=False)
    assert pypi.delai() == timedelta(days=3)


def test_sas_delai_se_donne_en_secondes(monkeypatch):
    monkeypatch.setenv("SAS_DELAI", "120")
    assert pypi.delai() == timedelta(minutes=2)


@pytest.mark.parametrize("brut", ["deux minutes", "0", "-60", "1.5", "inf"])
def test_un_sas_delai_invalide_est_refuse_plutot_que_d_annuler_l_attente(monkeypatch, brut):
    monkeypatch.setenv("SAS_DELAI", brut)
    with pytest.raises(ValueError, match="SAS_DELAI"):
        pypi.delai()

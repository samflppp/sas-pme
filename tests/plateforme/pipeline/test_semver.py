"""Versions et plages npm (semver) : ce que le pipeline npm utilise pour choisir une version."""
import pytest

from plateforme.pipeline import semver


def test_les_versions_se_trient_comme_npm():
    vs = ["1.10.0", "1.2.0", "1.2.0-beta.2", "1.2.0-beta.10", "1.2.0-alpha", "0.9.9"]
    assert sorted(vs, key=semver.cle) == [
        "0.9.9", "1.2.0-alpha", "1.2.0-beta.2", "1.2.0-beta.10", "1.2.0", "1.10.0"]


def test_une_preversion_est_reconnue_et_une_version_illisible_refusee():
    assert semver.preversion("1.0.0-rc.1") and not semver.preversion("1.0.0+build.5")
    assert semver.lire("v1.2.3") == (1, 2, 3, ())
    for mauvaise in ("1.2", "latest", "1.2.3.4", "01.2.3"):
        assert semver.lire(mauvaise) is None


@pytest.mark.parametrize("plage, oui, non", [
    ("^1.2.3", ["1.2.3", "1.9.0"], ["1.2.2", "2.0.0", "1.3.0-beta.1"]),
    ("^0.2.3", ["0.2.3", "0.2.9"], ["0.3.0"]),
    ("^0.0.3", ["0.0.3"], ["0.0.4"]),
    ("~1.2.3", ["1.2.3", "1.2.9"], ["1.3.0"]),
    ("~1.2", ["1.2.0", "1.2.7"], ["1.3.0"]),
    (">=1.2.0 <2", ["1.2.0", "1.99.0"], ["2.0.0", "1.1.9"]),
    ("1.x", ["1.0.0", "1.5.2"], ["2.0.0"]),
    ("1.2.x", ["1.2.0", "1.2.9"], ["1.3.0"]),
    ("*", ["0.0.1", "9.9.9"], ["1.0.0-beta"]),
    ("", ["1.0.0"], []),
    ("1.2.3", ["1.2.3"], ["1.2.4"]),
    ("=1.2.3", ["1.2.3"], ["1.2.4"]),
    ("1.2.3 - 2.3.4", ["1.2.3", "2.3.4"], ["2.3.5"]),
    ("^1.0.0 || ^3.0.0", ["1.5.0", "3.1.0"], ["2.0.0"]),
])
def test_les_plages_courantes(plage, oui, non):
    p = semver.Plage(plage)
    assert all(p.contient(v) for v in oui)
    assert not any(p.contient(v) for v in non)


@pytest.mark.parametrize("plage", ["latest", "git+https://x/y.git", "file:../x", "npm:autre@1",
                                   "github:user/repo", "^1.2.3 ||", "<<1"])
def test_une_plage_hors_semver_est_refusee(plage):
    with pytest.raises(ValueError):
        semver.Plage(plage)

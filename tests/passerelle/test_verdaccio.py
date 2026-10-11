"""Client Verdaccio de la passerelle, contre un vrai Verdaccio sans source amont (Docker)."""
import io
import json
import secrets
import shutil
import socket
import subprocess
import tarfile
import time

import httpx
import pytest

from passerelle.verdaccio import ErreurDepot, Verdaccio, package_json

CONFIG = """storage: /verdaccio/storage
auth:
  htpasswd:
    file: /verdaccio/storage/htpasswd
    max_users: 1
uplinks: {}
packages:
  '@*/*': {access: $all, publish: recepteur, unpublish: recepteur}
  '**': {access: $all, publish: recepteur, unpublish: recepteur}
log: {type: stdout, format: json, level: warn}
"""


def tgz(nom: str, version: str, code: str = "module.exports = 1;") -> bytes:
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w:gz") as t:
        for f, texte in {"package.json": json.dumps({"name": nom, "version": version}),
                         "index.js": code}.items():
            o = texte.encode()
            i = tarfile.TarInfo(f"package/{f}")
            i.size = len(o)
            t.addfile(i, io.BytesIO(o))
    return b.getvalue()


def test_le_package_json_est_lu_en_memoire():
    assert package_json(tgz("@org/x", "1.0.0")) == {"name": "@org/x", "version": "1.0.0"}
    with pytest.raises(ErreurDepot):
        package_json(b"pas une archive")


def _docker_ok() -> bool:
    return bool(shutil.which("docker")) and \
        subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.fixture(scope="module")
def verdaccio(tmp_path_factory):
    if not _docker_ok():
        pytest.skip("Docker indisponible")
    conf = tmp_path_factory.mktemp("verdaccio")
    (conf / "config.yaml").write_text(CONFIG)
    conf.chmod(0o755)                         # Verdaccio tourne sous son propre utilisateur
    (conf / "config.yaml").chmod(0o644)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    nom = f"sas-verdaccio-test-{secrets.token_hex(3)}"
    r = subprocess.run(["docker", "run", "-d", "--name", nom, "-p", f"127.0.0.1:{port}:4873",
                        "-v", f"{conf}:/verdaccio/conf:ro", "verdaccio/verdaccio:6"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"Verdaccio indisponible : {r.stderr[:100]}")
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{url}/-/ping", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        else:
            journal = subprocess.run(["docker", "logs", nom], capture_output=True, text=True)
            pytest.fail(f"Verdaccio n'a pas démarré : {journal.stderr[-300:]}")
        jeton = httpx.put(f"{url}/-/user/org.couchdb.user:recepteur",
                          json={"name": "recepteur", "password": secrets.token_hex(16)}).json()["token"]
        yield url, Verdaccio(url, jeton)
    finally:
        subprocess.run(["docker", "rm", "-f", nom], capture_output=True)


@pytest.mark.docker
def test_publier_retirer_et_latest_contre_un_vrai_verdaccio(verdaccio):
    url, vd = verdaccio
    archives = {v: tgz("@org/outil", v) for v in ("1.0.0", "1.1.0", "1.0.5")}
    for v, octets in archives.items():
        vd.publier("@org/outil", v, f"outil-{v}.tgz", octets)
    vd.publier("@org/outil", "1.1.0", "outil-1.1.0.tgz", archives["1.1.0"])   # idempotent
    with pytest.raises(ErreurDepot, match="autre archive"):
        vd.publier("@org/outil", "1.1.0", "outil-1.1.0.tgz", tgz("@org/outil", "1.1.0", "x"))
    assert vd.versions("@org/outil") == ["1.0.0", "1.0.5", "1.1.0"]
    assert httpx.get(f"{url}/@org%2Foutil").json()["dist-tags"]["latest"] == "1.1.0"
    assert vd.retirer("@org/outil", "1.1.0") == ["outil-1.1.0.tgz"]
    assert httpx.get(f"{url}/@org/outil/-/outil-1.1.0.tgz").status_code == 404
    assert httpx.get(f"{url}/@org%2Foutil").json()["dist-tags"]["latest"] == "1.0.5"
    assert vd.retirer("@org/outil", "9.9.9") == []


@pytest.mark.docker
def test_sans_source_amont_et_sans_jeton_rien_ne_s_ecrit(verdaccio):
    url, _ = verdaccio
    assert httpx.get(f"{url}/left-pad").status_code == 404           # aucun repli vers npmjs
    intrus = Verdaccio(url, "jeton-faux")
    with pytest.raises(ErreurDepot):
        intrus.publier("intrus", "1.0.0", "intrus-1.0.0.tgz", tgz("intrus", "1.0.0"))
    assert httpx.get(f"{url}/intrus").status_code == 404


@pytest.mark.docker
def test_une_archive_qui_ment_sur_son_nom_est_refusee(verdaccio):
    _, vd = verdaccio
    with pytest.raises(ErreurDepot, match="annonce"):
        vd.publier("vrai-nom", "1.0.0", "vrai-nom-1.0.0.tgz", tgz("autre-nom", "1.0.0"))


def test_la_passerelle_ne_depend_pas_de_la_plateforme():
    """installer.sh ne copie que commun/ et passerelle/ sur la passerelle."""
    import sys
    code = ("import sys, passerelle.recepteur, passerelle.verdaccio, passerelle.inventaire_npm;"
            "passerelle.verdaccio._cle('1.0.0');"
            "print([m for m in sys.modules if m.startswith('plateforme')])")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert r.stdout.strip() == "[]"


def test_latest_suit_l_ordre_semver_et_pas_celui_du_texte():
    from passerelle.verdaccio import _cle
    assert sorted(["1.10.0", "1.9.0", "1.10.0-beta.1", "2.0.0"], key=_cle) == [
        "1.9.0", "1.10.0-beta.1", "1.10.0", "2.0.0"]

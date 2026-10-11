"""WireGuard, mode « plateforme hors site » (C, extension M2) : le récepteur n'est joignable que par
le tunnel, chaque clé privée naît sur son hôte, la passerelle ne gagne aucune route vers Internet."""
import base64
import importlib.util
import re
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

INFRA = Path(__file__).resolve().parents[2] / "infra"
SCRIPT = INFRA / "aws" / "installer_wireguard.sh"


def charger():
    spec = importlib.util.spec_from_file_location("wg_rendre", INFRA / "wireguard" / "rendre.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cle_publique() -> str:
    brut = X25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(brut).decode()


def sections(texte: str) -> dict[str, dict[str, str]]:
    out, courante = {}, None
    for ligne in texte.splitlines():
        if m := re.fullmatch(r"\[(\w+)\]", ligne.strip()):
            courante = out.setdefault(m[1], {})
        elif "=" in ligne and not ligne.lstrip().startswith("#"):
            k, v = ligne.split("=", 1)
            courante[k.strip()] = v.strip()
    return out


def test_la_passerelle_appelle_la_plateforme_et_n_accepte_qu_elle():
    wg, cle_plat = charger(), cle_publique()
    netdev, network = wg.rendre("passerelle", cle_pair=cle_plat)
    s = sections(netdev)
    assert s["NetDev"] == {"Name": "wg0", "Kind": "wireguard",
                           "Description": s["NetDev"]["Description"]}
    assert s["WireGuard"]["PrivateKeyFile"] == "/etc/systemd/network/wg0.key"
    assert "ListenPort" not in s["WireGuard"]                    # elle n'écoute pas : elle appelle
    assert s["WireGuardPeer"] == {"PublicKey": cle_plat, "AllowedIPs": "10.99.0.1/32",
                                  "Endpoint": "10.42.1.10:51820", "PersistentKeepalive": "25"}
    n = sections(network)
    assert n["Match"] == {"Name": "wg0"} and n["Network"] == {"Address": "10.99.0.2/24"}


def test_la_plateforme_ecoute_et_n_accepte_que_la_passerelle():
    wg, cle_pass = charger(), cle_publique()
    netdev, network = wg.rendre("plateforme", cle_pair=cle_pass)
    s = sections(netdev)
    assert s["WireGuard"]["ListenPort"] == "51820"
    assert s["WireGuardPeer"] == {"PublicKey": cle_pass, "AllowedIPs": "10.99.0.2/32"}
    assert sections(network)["Network"] == {"Address": "10.99.0.1/24"}


def test_aucune_route_par_defaut_dans_le_tunnel():
    """AllowedIPs = le seul pair : la passerelle ne peut rien router vers Internet par la plateforme."""
    wg = charger()
    for role in ("plateforme", "passerelle"):
        netdev, network = wg.rendre(role, cle_pair=cle_publique())
        assert "0.0.0.0/0" not in netdev + network
        assert "Gateway" not in network and "IPForward" not in network


@pytest.mark.parametrize("cle", [
    "", "pas-une-cle", "A" * 43, base64.b64encode(b"x" * 31).decode(),
    cle_publique() + "\nEndpoint=6.6.6.6:1",                     # injection d'une ligne
])
def test_une_cle_publique_mal_formee_est_refusee(cle):
    with pytest.raises(ValueError):
        charger().rendre("passerelle", cle_pair=cle)


def test_un_role_inconnu_est_refuse():
    with pytest.raises(ValueError):
        charger().rendre("serveur", cle_pair=cle_publique())


def test_la_ligne_de_commande_ecrit_les_deux_fichiers(tmp_path):
    cle = cle_publique()
    subprocess.run(["python3", "-I", str(INFRA / "wireguard" / "rendre.py"), "passerelle", cle,
                    str(tmp_path)], check=True)
    assert cle in (tmp_path / "90-sas-wg0.netdev").read_text()
    assert "10.99.0.2/24" in (tmp_path / "90-sas-wg0.network").read_text()


def test_la_cle_tiree_par_openssl_est_celle_de_wireguard(tmp_path):
    """Le script tire les clés avec openssl (aucun paquet à installer hors ligne) : la clé publique
    qu'il en extrait doit être celle que WireGuard dérive de la clé privée (X25519 brut, base64)."""
    pem = tmp_path / "x25519.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "X25519", "-out", str(pem)], check=True)
    prive = subprocess.run(f"openssl pkey -in {pem} -outform DER | tail -c 32 | base64",
                           shell=True, check=True, capture_output=True, text=True).stdout.strip()
    public = subprocess.run(f"openssl pkey -in {pem} -pubout -outform DER | tail -c 32 | base64",
                            shell=True, check=True, capture_output=True, text=True).stdout.strip()
    attendu = X25519PrivateKey.from_private_bytes(base64.b64decode(prive)).public_key() \
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    assert base64.b64decode(public) == attendu
    charger().rendre("passerelle", cle_pair=public)              # format accepté par le rendu


def test_le_script_est_valide_et_garde_les_cles_privees_sur_leur_hote():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    texte = SCRIPT.read_text()
    assert "openssl genpkey -algorithm X25519" in texte
    assert "umask 077" in texte
    # Seules les clés publiques voyagent : aucune lecture de wg0.key ni du PEM hors de l'hôte.
    for ligne in texte.splitlines():
        if re.search(r"\bcat\b.*(wg0\.key|x25519\.pem)", ligne):
            pytest.fail(f"clé privée lue pour sortir de son hôte : {ligne}")
    assert "-pubout" in texte


def test_le_script_ferme_le_recepteur_hors_du_tunnel_et_le_verifie():
    texte = SCRIPT.read_text()
    assert re.search(r"ufw delete allow from 10\.42\.1\.10 to any port 8443", texte)
    assert re.search(r"ufw allow in on wg0 from 10\.99\.0\.1 to any port 8443", texte)
    assert "10.99.0.2 passerelle" in texte                       # le certificat (DNS:passerelle) reste bon
    assert "https://10.42.2.10:8443" in texte                    # le chemin direct doit échouer
    assert "IpProtocol=udp,FromPort=51820,ToPort=51820" in texte  # groupes de sécurité AWS
    assert "SAS_RELAIS_AMONT=10.99.0.1:3129" in texte and "SAS_RELAIS_ECOUTE=10.99.0.1:3129" in texte


def test_le_script_sait_revenir_au_reseau_local():
    """Le mode réseau local reste la démo garantie : un retour en une commande."""
    texte = SCRIPT.read_text()
    assert re.search(r'"\$\{1:-\}" == "local"', texte)
    assert "ufw allow from 10.42.1.10 to any port 8443" in texte


def test_le_recepteur_ecoute_sur_l_adresse_reglee_et_le_tunnel_la_change():
    """En mode tunnel, le récepteur n'écoute plus sur le réseau local : pare-feu ET socket."""
    service = (INFRA / "passerelle" / "recepteur.service").read_text()
    assert "Environment=SAS_RECEPTEUR_HOTE=10.42.2.10" in service      # réseau local par défaut
    assert "--host ${SAS_RECEPTEUR_HOTE}" in service
    assert "SAS_RECEPTEUR_HOTE=10.99.0.2" in SCRIPT.read_text()

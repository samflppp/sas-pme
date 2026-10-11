"""Agent d'installation du serveur de démo (A pour C, conception-demo § 1) : il ne lance pip que sur
une demande signée par la plateforme, récente, jamais vue, au nom de paquet valide."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from passerelle import installation
from plateforme.signature import ed25519

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "serveur" / "agent_installation.py"
MAINTENANT = datetime(2026, 10, 11, 9, 5, tzinfo=timezone.utc)


def charger():
    spec = importlib.util.spec_from_file_location("agent_installation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def env(tmp_path):
    cle = ed25519.generer_cle(tmp_path / "plateforme.pem")
    return charger(), cle, ed25519.cle_publique_pem(cle), tmp_path / "etat"


def entree(cle, n=1, nom="demo-horodatage", nonce=None, age=timedelta(seconds=2)):
    d = installation.DemandeInstallation(nom=nom, demande=n, emis_le=MAINTENANT - age,
                                         nonce=nonce or f"{n:032x}")
    t, sig = installation.signer(d, cle)
    return {"n": n, "demande": t, "signature": sig}


def tour(agent, pem, etat, entrees):
    lances = []
    agent.tour(lambda apres: [e for e in entrees if e["n"] > apres], pem, etat,
               executer=lances.append, maintenant=MAINTENANT)
    return lances


def test_une_demande_signee_lance_pip_sur_le_nom_demande(env):
    agent, cle, pem, etat = env
    assert tour(agent, pem, etat, [entree(cle)]) == ["demo-horodatage"]


def test_une_demande_n_est_executee_qu_une_fois_meme_apres_redemarrage(env):
    agent, cle, pem, etat = env
    e = entree(cle)
    assert tour(agent, pem, etat, [e]) == ["demo-horodatage"]
    assert tour(charger(), pem, etat, [e]) == []                    # « dernier » relu sur disque
    rejouee = {**e, "n": 2}                                           # même demande, autre rang
    assert tour(agent, pem, etat, [rejouee]) == []                  # le nonce est déjà vu


def test_une_demande_forgee_n_est_jamais_executee(env, tmp_path):
    agent, _, pem, etat = env
    usurpateur = ed25519.generer_cle(tmp_path / "usurpateur.pem")
    assert tour(agent, pem, etat, [entree(usurpateur)]) == []


def test_une_demande_trop_vieille_n_est_pas_executee(env):
    agent, cle, pem, etat = env
    assert tour(agent, pem, etat, [entree(cle, age=timedelta(minutes=11))]) == []


def test_une_demande_alteree_n_est_pas_executee(env):
    agent, cle, pem, etat = env
    e = entree(cle)
    e["demande"] = e["demande"].replace("demo-horodatage", "demo-horodatagf")
    assert tour(agent, pem, etat, [e]) == []


def test_un_nom_d_option_pip_n_est_jamais_passe_a_pip(env):
    """Même signé (clé volée), « --index-url=… » n'est pas un nom de paquet."""
    agent, cle, pem, etat = env
    d = installation.DemandeInstallation.model_construct(
        type="installation", ecosysteme="pypi", nom="--index-url=http://pirate", demande=1,
        emis_le=MAINTENANT, nonce="f" * 32)
    t = json.dumps(d.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    import base64
    sig = base64.b64encode(cle.sign(installation.PREFIXE + t.encode())).decode()
    assert tour(agent, pem, etat, [{"n": 1, "demande": t, "signature": sig}]) == []


def test_la_commande_pip_vise_la_passerelle_seulement(env, monkeypatch):
    agent, *_ = env
    vus = []
    monkeypatch.setattr(agent.subprocess, "run", lambda cmd, **k: vus.append((cmd, k)))
    agent.installer("demo-horodatage", "http://10.42.2.10:8080/simple/")
    cmd, k = vus[0]
    assert cmd[-1] == "demo-horodatage" and "--upgrade" in cmd
    assert cmd[cmd.index("--index-url") + 1] == "http://10.42.2.10:8080/simple/"
    assert "--extra-index-url" not in cmd and k.get("timeout")
    # index en HTTP sur le réseau privé : pip l'ignore s'il n'est pas déclaré de confiance
    assert cmd[cmd.index("--trusted-host") + 1] == "10.42.2.10"


def test_l_agent_n_installe_que_des_roues(env, monkeypatch):
    """Une archive source exécute son setup.py à l'installation : une demande signée par une
    plateforme prise deviendrait une exécution de code sur le serveur. Roues seulement."""
    agent, *_ = env
    vus = []
    monkeypatch.setattr(agent.subprocess, "run", lambda cmd, **k: vus.append(cmd))
    agent.installer("demo-horodatage", "http://10.42.2.10:8080/simple/")
    assert "--only-binary=:all:" in vus[0]


# --- l'agent réessaie : la version n'est servie qu'après l'analyse (minutes) -------------------
def test_un_pip_qui_echoue_est_relance_jusqu_a_ce_que_la_version_soit_servie(env):
    """À la demande, la version n'est pas encore publiée : pip échoue. L'agent la retient et relance
    pip jusqu'à ce qu'il réussisse ; personne n'a rien à refaire à la main."""
    agent, cle, pem, etat = env
    servie = {"oui": False}
    lances = []

    def executer(nom):
        lances.append(nom)
        return servie["oui"]

    agent.tour(lambda apres: [entree(cle)] if apres < 1 else [], pem, etat, executer,
               maintenant=MAINTENANT)
    assert lances == ["demo-horodatage"]
    agent.reessayer(etat, executer, MAINTENANT + timedelta(seconds=5))     # trop tôt
    assert lances == ["demo-horodatage"]
    agent.reessayer(etat, executer, MAINTENANT + timedelta(seconds=30))    # toujours pas servie
    assert lances == ["demo-horodatage"] * 2
    servie["oui"] = True
    agent.reessayer(etat, executer, MAINTENANT + timedelta(seconds=60))
    assert lances == ["demo-horodatage"] * 3
    agent.reessayer(etat, executer, MAINTENANT + timedelta(minutes=5))     # installée : fini
    assert lances == ["demo-horodatage"] * 3


def test_l_attente_survit_a_un_redemarrage_et_s_arrete_au_bout_de_la_patience(env):
    agent, cle, pem, etat = env
    lances = []
    agent.tour(lambda apres: [entree(cle)] if apres < 1 else [], pem, etat,
               lambda nom: lances.append(nom) or False, maintenant=MAINTENANT)
    autre = charger()                                                      # redémarrage
    autre.reessayer(etat, lambda nom: lances.append(nom) or False,
                    MAINTENANT + timedelta(minutes=1))
    assert len(lances) == 2
    autre.reessayer(etat, lambda nom: lances.append(nom) or False,
                    MAINTENANT + timedelta(hours=2))                      # bloquée : on lâche
    autre.reessayer(etat, lambda nom: lances.append(nom) or False,
                    MAINTENANT + timedelta(hours=3))
    assert len(lances) == 2


def test_installer_dit_si_pip_a_reussi(env, monkeypatch):
    agent, *_ = env
    for code, attendu in ((0, True), (1, False)):
        monkeypatch.setattr(agent.subprocess, "run",
                            lambda cmd, **k: subprocess_resultat(code))
        assert agent.installer("demo-horodatage", "http://10.42.2.10:8080/simple/") is attendu


def subprocess_resultat(code):
    import subprocess
    return subprocess.CompletedProcess([], code)

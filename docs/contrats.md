# Contrats entre les parties

Ces contrats permettent à chacun de coder seul sans attendre les autres. Ils vivent dans le paquet
Python `commun/` (écrit en M0) et sont décrits ici. **Un contrat ne change que par une PR relue par les
trois.** Chaque partie code contre le contrat, et contre un faux (stub) de l'autre partie tant que la
vraie n'existe pas.

## 1. Types partagés (`commun/modeles.py`)

```python
class Ecosysteme(StrEnum): PYPI = "pypi"; NPM = "npm"

class Etat(StrEnum):
    NOUVELLE = "nouvelle"; EN_ATTENTE = "en_attente"; EN_ANALYSE = "en_analyse"
    A_REVOIR = "a_revoir"; APPROUVEE = "approuvee"; BLOQUEE = "bloquee"
    PUBLIEE = "publiee"; REVOQUEE = "revoquee"

class Niveau(StrEnum): INFO = "info"; MOYEN = "moyen"; FORT = "fort"; BLOQUANT = "bloquant"

class Source(StrEnum):
    STATIQUE = "statique"; SANDBOX = "sandbox"; LLM = "llm"; VEILLE = "veille"; HUMAIN = "humain"

class Version(BaseModel):
    ecosysteme: Ecosysteme; nom: str; version: str
    publiee_le: datetime          # date de publication sur PyPI/npm
    detectee_le: datetime
    etat: Etat

class Signal(BaseModel):
    ecosysteme: Ecosysteme; nom: str; version: str
    source: Source; niveau: Niveau; sorte: str        # ex. "typosquat", "dns_exfil", "lit_leurre"
    preuve: dict                                      # {"fichier","ligne","extrait","url","ref_rag"}
    structure: bool = True                            # False pour un article de source libre

class RapportSandbox(BaseModel):
    requetes_dns: list[str]; connexions: list[str]    # "hote:port"
    fichiers_sensibles: list[str]; leurres_lus: list[str]
    processus: list[str]; code_sortie: int; duree_s: float; delai_depasse: bool

class Verdict(BaseModel):
    etat: Etat                                        # approuvee | a_revoir | bloquee
    raison: str                                       # une phrase en français
    signaux: list[Signal]
    explication_llm: str = ""; refs_rag: list[str] = []

class EntreeInventaire(BaseModel):
    ecosysteme: Ecosysteme; nom: str; version: str; telechargements: int; dernier: datetime | None

class FichierManifeste(BaseModel): nom: str; sha256: str    # 64 caractères hexadécimaux
class Manifeste(BaseModel): ...                             # voir § 4
def canonique(m: Manifeste) -> bytes                        # octets exacts à signer
```

**Règles tenues par les types** (une tentative lève `ValidationError`) :
- un `Signal` de source `LLM` ne peut pas être `BLOQUANT` ;
- un `Signal` de source `VEILLE` non structuré (un article) ne peut pas être `BLOQUANT` ;
- un `Verdict` ne conclut que `APPROUVEE`, `A_REVOIR` ou `BLOQUEE` ;
- tous les modèles sont immuables et refusent les champs inconnus.

## 2. Pipeline → base de données (B appelle A)

`plateforme/db/acces.py`, écrit par A. B ne fait jamais de SQL lui-même.

```python
def versions_a_traiter(maintenant: datetime) -> list[Version]   # en_attente dont le délai est écoulé
def enregistrer_version(v: Version) -> bool                      # True si nouvelle
def changer_etat(eco, nom, version, etat: Etat, raison: str) -> None
def ajouter_signal(s: Signal) -> int
def enregistrer_verdict(eco, nom, version, v: Verdict) -> None
def enregistrer_rapport_sandbox(eco, nom, version, r: RapportSandbox) -> None
def inventaire() -> list[tuple[Ecosysteme, str, str]]            # (éco, nom, version utilisée)
```

## 3. Pipeline → sandbox (B appelle C)

`plateforme/sandbox/__init__.py`, écrit par C. **Stub M0 :** renvoie un rapport vide.

```python
def executer(ecosysteme: Ecosysteme, archive: Path, module: str, duree_max_s: int = 120) -> RapportSandbox
```

## 4. Plateforme → passerelle (A et B appellent C)

`plateforme/signature/__init__.py` (signer) et l'API du récepteur de la passerelle, écrits par C.

```python
def publier(ecosysteme, nom, version, archives: list[Path], verdict_id: int) -> None   # signe + POST
def revoquer(ecosysteme, nom, version, raison: str) -> None
def lire_inventaire() -> list[EntreeInventaire]
```

**Manifeste signé** (JSON canonique, clés triées, sans espaces) :

```json
{
  "type": "publication",
  "ecosysteme": "pypi",
  "nom": "requests",
  "version": "2.32.4",
  "fichiers": [{"nom": "requests-2.32.4-py3-none-any.whl", "sha256": "…"}],
  "verdict_id": 42,
  "approuve_le": "2026-10-11T09:00:00Z",
  "emis_le": "2026-10-11T09:00:05Z",
  "nonce": "8f1c…"
}
```

**L'API de la passerelle** (TLS mutuel sur `:8443`, certificat client de la plateforme exigé) :

| Méthode | Chemin | Corps | Réponses |
|---|---|---|---|
| POST | `/v1/publish` | multipart : `manifeste` (JSON), `signature` (base64 Ed25519), archives | 201 publié · 400 hash différent · 401 signature invalide · 409 nonce déjà vu |
| POST | `/v1/revoke` | `manifeste` de type `revocation` + `signature` | 200 retiré · 401 |
| GET | `/v1/inventory` | — | 200 `[{"ecosysteme","nom","version","telechargements","dernier"}]` |
| GET | `/v1/health` | — | 200 `{"pypi": true, "npm": true}` |

**Règles de la passerelle :**
- signature vérifiée avec la seule clé publique de la plateforme, posée à l'installation ;
- chaque fichier hashé et comparé au manifeste ;
- un manifeste dont `emis_le` a plus de 10 min est refusé ;
- un nonce déjà vu est refusé.

## 5. Interface web ↔ pipeline (A et B)

- La page « demander un paquet » appelle `pipeline.demander(ecosysteme, nom)` (B). Cette fonction choisit
  la dernière version publiée depuis plus de 3 jours et l'enregistre.
- Le bouton « approuver » ou « bloquer » d'une version à revoir appelle `pipeline.decision_humaine(...)`
  (B), qui écrit un signal `HUMAIN` puis applique la politique.

## 6. LLM (B, interne à B)

- **Appel :** `POST http://127.0.0.1:11434/api/chat`, avec `format` = le schéma JSON de
  `VerdictLLM` et une température de 0.
- **Entrées :** constats, rapport de sandbox, changelog et passages du RAG, entre balises `<donnee>`.
- **Sortie :** une liste de signaux `LLM` (niveau au plus `FORT`), une explication en français et les
  références RAG citées.
- Une réponse hors schéma est ignorée et journalisée.

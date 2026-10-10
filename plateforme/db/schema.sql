-- Schéma de la plateforme (A). Les objets métier sont stockés en JSON (modèles de commun/modeles.py).

CREATE TABLE IF NOT EXISTS versions (
    ecosysteme  TEXT NOT NULL,
    nom         TEXT NOT NULL,
    version     TEXT NOT NULL,
    publiee_le  TEXT NOT NULL,   -- ISO 8601 UTC
    detectee_le TEXT NOT NULL,
    etat        TEXT NOT NULL,
    raison      TEXT NOT NULL DEFAULT '',
    maj_le      TEXT NOT NULL,
    PRIMARY KEY (ecosysteme, nom, version)
);
CREATE INDEX IF NOT EXISTS versions_etat ON versions (etat, publiee_le);

CREATE TABLE IF NOT EXISTS signaux (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ecosysteme TEXT NOT NULL, nom TEXT NOT NULL, version TEXT NOT NULL,
    donnees TEXT NOT NULL,       -- Signal en JSON
    cree_le TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS signaux_version ON signaux (ecosysteme, nom, version);

CREATE TABLE IF NOT EXISTS verdicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ecosysteme TEXT NOT NULL, nom TEXT NOT NULL, version TEXT NOT NULL,
    donnees TEXT NOT NULL,       -- Verdict en JSON
    cree_le TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rapports_sandbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ecosysteme TEXT NOT NULL, nom TEXT NOT NULL, version TEXT NOT NULL,
    donnees TEXT NOT NULL,       -- RapportSandbox en JSON
    cree_le TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventaire (
    ecosysteme TEXT NOT NULL, nom TEXT NOT NULL, version TEXT NOT NULL,
    telechargements INTEGER NOT NULL,
    dernier TEXT,
    PRIMARY KEY (ecosysteme, nom, version)
);

-- Journal append-only, chaîné : hash = sha256(hash_precedent + json canonique de l'entrée).
CREATE TABLE IF NOT EXISTS journal (
    seq    INTEGER PRIMARY KEY AUTOINCREMENT,
    a      TEXT NOT NULL,
    acteur TEXT NOT NULL,
    action TEXT NOT NULL,
    sujet  TEXT NOT NULL,
    charge TEXT NOT NULL,
    prec   TEXT NOT NULL,
    hash   TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS journal_sans_modification BEFORE UPDATE ON journal
BEGIN SELECT RAISE(ABORT, 'journal append-only'); END;
CREATE TRIGGER IF NOT EXISTS journal_sans_suppression BEFORE DELETE ON journal
BEGIN SELECT RAISE(ABORT, 'journal append-only'); END;

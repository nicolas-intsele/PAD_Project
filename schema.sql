-- ===================================================================
-- Script de création de la base de données décisionelle
-- Plateforme d'analyse des performances des opérations navires - PAD
-- SGBD cible : PostgreSQL 15+
-- ===================================================================

-- ===================================================================
-- 1. TABLES DE REFERENCE / DIMENSIONS
-- ===================================================================

CREATE TABLE type_navire (
    id_type SERIAL PRIMARY KEY,
    libelle VARCHAR(50) NOT NULL,
    categorie VARCHAR(50)
);

CREATE TABLE compagnie_maritime (
    id_compagnie SERIAL PRIMARY KEY,
    raison_sociale VARCHAR(100) NOT NULL,
    pays VARCHAR(50)
);

CREATE TABLE terminal (
    id_terminal SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    specialite VARCHAR(100)
);

CREATE TABLE agent_maritime (
    id_agent SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    contact VARCHAR(100)
);

CREATE TABLE service_nautique (
    id_service SERIAL PRIMARY KEY,
    type_service VARCHAR(100) NOT NULL,
    duree_moyenne_ref NUMERIC(6,2)
);

CREATE TABLE calendrier (
    id_date SERIAL PRIMARY KEY,
    date_calendaire DATE NOT NULL,
    mois SMALLINT NOT NULL,
    trimestre SMALLINT NOT NULL,
    annee SMALLINT NOT NULL,
    jour_semaine VARCHAR(15) NOT NULL
);

CREATE TABLE role (
    id_role SERIAL PRIMARY KEY,
    libelle VARCHAR(100) NOT NULL,
    permissions JSONB
);

CREATE TABLE quai (
    id_quai SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    longueur NUMERIC(6,2) NOT NULL,
    tirant_eau_max NUMERIC(6,2) NOT NULL,
    id_terminal     INTEGER NOT NULL REFERENCES terminal(id_terminal)
);

CREATE TABLE navire (
    id_navire SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    imo VARCHAR(20) NOT NULL,
    pavillon VARCHAR(60) NOT NULL,
    longueur NUMERIC(6,2) NOT NULL,
    jauge_brute NUMERIC(6,2) NOT NULL,
    id_type INTEGER NOT NULL REFERENCES type_navire(id_type),
    id_compagnie INTEGER NOT NULL REFERENCES compagnie_maritime(id_compagnie)
);

CREATE TABLE utilisateur (
    id_utilisateur SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    mot_de_passe VARCHAR(150) NOT NULL, 
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    id_role INTEGER NOT NULL REFERENCES role(id_role)
);


-- ==============================================================
-- 2. TABLES DE FAITS
-- ==============================================================
CREATE TABLE escale (
    id_escale SERIAL PRIMARY KEY,
    date_arrivee TIMESTAMP NOT NULL,
    date_accostage TIMESTAMP,
    date_appareillage TIMESTAMP,
    date_depart TIMESTAMP,
    temps_attente NUMERIC(6,2),
    temps_sejour NUMERIC(6,2),
    temps_pilotage NUMERIC(6,2),
    temps_accostage NUMERIC(6,2),
    staut VARCHAR(50) NOT NULL DEFAULT 'planifiée',
    id_navire INTEGER NOT NULL REFERENCES navire(id_navire),
    id_agent INTEGER NOT NULL REFERENCES agent_maritime(id_agent),
    id_quai INTEGER NOT NULL REFERENCES quai(id_quai),
    id_date INTEGER NOT NULL REFERENCES calendrier(id_date)
);
CREATE INDEX idx_escale_navire ON escale(id_navire);
CREATE INDEX idx_escale_quai   ON escale(id_quai);
CREATE INDEX idx_escale_date   ON escale(id_date);

CREATE TABLE mobiliser (
    id_escale INTEGER NOT NULL REFERENCES escale(id_escale),
    id_service INTEGER NOT NULL REFERENCES service_nautique(id_service),
    duree_reelle NUMERIC(6,2),
    ordre_intervention SMALLINT,
    PRIMARY KEY (id_escale, id_service)
);


-- ================================================================
-- 3. KPIs ET ALERTES
-- ================================================================

CREATE TABLE kpi (
    id_kpi SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    libelle VARCHAR(150) NOT NULL,
    categorie VARCHAR(50) NOT NULL,
    unite VARCHAR(20),
    formule TEXT
);

CREATE TABLE valeur_kpi (
    id_valeur SERIAL PRIMARY KEY,
    id_kpi INTEGER NOT NULL REFERENCES kpi(id_kpi),
    id_date INTEGER NOT NULL REFERENCES calendrier(id_date),
    valeur NUMERIC(12,3) NOT NULL,
    date_calcul TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (id_kpi, id_date)
);

CREATE TABLE seuil_alerte (
    id_seuil SERIAL PRIMARY KEY,
    id_kpi INTEGER NOT NULL REFERENCES kpi(id_kpi),
    valeur_min NUMERIC(12,3),
    valeur_max NUMERIC(12,3),
    niveau_gravite VARCHAR(20) NOT NULL
);

CREATE TABLE alerte (
    id_alerte SERIAL PRIMARY KEY,
    id_seuil INTEGER NOT NULL REFERENCES seuil_alerte(id_seuil),
    id_escale INTEGER REFERENCES escale(id_escale),
    type_alerte VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    date_declenchement TIMESTAMP NOT NULL DEFAULT now(),
    statut VARCHAR(20) NOT NULL DEFAULT 'ouverte'
);


-- =========================================================================
-- 4. REPORTING ET ADMINISTRATION
-- =========================================================================

CREATE TABLE rapport (
    id_rapport          SERIAL PRIMARY KEY,
    id_utilisateur      INTEGER NOT NULL REFERENCES utilisateur(id_utilisateur),
    type_rapport        VARCHAR(30) NOT NULL,
    periode             VARCHAR(30) NOT NULL,
    date_generation     TIMESTAMP NOT NULL DEFAULT now(),
    format              VARCHAR(10) NOT NULL
);

CREATE TABLE rapport_kpi (
    id_rapport      INTEGER NOT NULL REFERENCES rapport(id_rapport) ON DELETE CASCADE,
    id_kpi          INTEGER NOT NULL REFERENCES kpi(id_kpi),
    PRIMARY KEY (id_rapport, id_kpi)
);

CREATE TABLE journal_import (
    id_import       SERIAL PRIMARY KEY,
    id_utilisateur  INTEGER NOT NULL REFERENCES utilisateur(id_utilisateur),
    source          VARCHAR(100) NOT NULL,
    date_import     TIMESTAMP NOT NULL DEFAULT now(),
    nb_lignes       INTEGER,
    statut          VARCHAR(20) NOT NULL,
    erreurs         TEXT
);

CREATE TABLE journal_action (
    id_log          SERIAL PRIMARY KEY,
    id_utilisateur  INTEGER NOT NULL REFERENCES utilisateur(id_utilisateur),
    action          VARCHAR(150) NOT NULL,
    date_action     TIMESTAMP NOT NULL DEFAULT now()
);


-- ============================================================================
-- 5. INDEX COMPLÉMENTAIRES POUR L'ANALYSE MULTIDIMENSIONNELLE
-- ============================================================================

CREATE INDEX idx_valeur_kpi_kpi_date ON valeur_kpi(id_kpi, id_date);
CREATE INDEX idx_alerte_statut       ON alerte(statut);
CREATE INDEX idx_navire_compagnie    ON navire(id_compagnie);
CREATE INDEX idx_quai_terminal       ON quai(id_terminal);

-- ============================================================================
-- Fin du script
-- ============================================================================
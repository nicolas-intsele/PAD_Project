"""
Catalogue des indicateurs de performance (Module 3).
11 KPI actifs après suppression de DISPONIBILITE_POSTES et CONGESTION.
"""

CATALOGUE_KPI = [
    # ── Trafic ──
    {
        "code": "TRAFIC_NB_ESCALES",
        "libelle": "Nombre d'escales",
        "categorie": "trafic",
        "unite": "escales",
        "formule": "Nombre total de lignes (une escale = une arrivée en rade).",
    },
    {
        "code": "TRAFIC_NB_ARRIVEES",
        "libelle": "Nombre d'arrivées à poste",
        "categorie": "trafic",
        "unite": "arrivées",
        "formule": "Nombre d'escales avec NAVIRE ARRIVEE POSTE renseigné.",
    },
    {
        "code": "TRAFIC_NB_DEPARTS",
        "libelle": "Nombre de départs",
        "categorie": "trafic",
        "unite": "départs",
        "formule": "Nombre d'escales avec NAVIRE APPAREILLE renseigné.",
    },
    # ── Temps ──
    {
        "code": "TEMPS_ATTENTE_MOYEN",
        "libelle": "Temps moyen d'attente",
        "categorie": "temps",
        "unite": "heures",
        "formule": "Moyenne de (PILOTE A BORD ARRIVEE − ARRIVEE RADE).",
    },
    {
        "code": "TEMPS_SEJOUR_MOYEN",
        "libelle": "Temps moyen de séjour à poste",
        "categorie": "temps",
        "unite": "heures",
        "formule": "Moyenne de (NAVIRE APPAREILLE − NAVIRE ARRIVEE POSTE).",
    },
    {
        "code": "TEMPS_PILOTAGE_MOYEN",
        "libelle": "Temps moyen de pilotage",
        "categorie": "temps",
        "unite": "heures",
        "formule": "Moyenne de (NAVIRE ARRIVEE POSTE − PILOTE A BORD ARRIVEE).",
    },
    {
        "code": "TEMPS_ACCOSTAGE_MOYEN",
        "libelle": "Temps moyen d'accostage",
        "categorie": "temps",
        "unite": "heures",
        "formule": "Moyenne de (PILOTE DEBARQUE ARRIVEE − NAVIRE ARRIVEE POSTE).",
    },
    # ── Infrastructures ──
    {
        "code": "INFRA_TAUX_OCCUPATION",
        "libelle": "Taux d'occupation moyen des postes",
        "categorie": "infrastructures",
        "unite": "%",
        "formule": "Moyenne par poste de (somme des séjours / heures du mois × 100).",
    },
    {
        "code": "INFRA_ROTATION_POSTES",
        "libelle": "Rotation moyenne des postes",
        "categorie": "infrastructures",
        "unite": "navires/poste",
        "formule": "Moyenne par poste du nombre de navires accostés dans la période.",
    },
    # ── Performance ──
    {
        "code": "PERF_PRODUCTIVITE",
        "libelle": "Productivité moyenne",
        "categorie": "performance",
        "unite": "t/h",
        "formule": "Moyenne de (tonnage total escale / temps_sejour) pour chaque escale.",
    },
    {
        "code": "PERF_DEBIT_POSTES",
        "libelle": "Débit moyen des postes",
        "categorie": "performance",
        "unite": "navires/jour",
        "formule": "Moyenne par poste de (nb navires / (somme séjours en heures / 24)).",
    },
]

SEUIL_CONGESTION_HEURES = 48  # conservé pour compatibilité ascendante

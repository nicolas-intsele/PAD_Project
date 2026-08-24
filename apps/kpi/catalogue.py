"""
Catalogue des indicateurss de performance
Chaque entrée sert à peupler la table KPI.
"""


CATALOGUE_KPI = [
    # ---- KPI Trafic ----
    {
        "code": "TRAFIC_NB_ESCALES",
        "libelle": "Nombre d'escales",
        "categorie": "trafic",
        "unite": "escales",
        "formule": "Nombre d'escales dont la date d'arrivée en rade est dans la période.",
    },
    {
        "code": "TRAFIC_NB_ARRIVEES",
        "libelle": "Nombre d'arrivées",
        "categorie": "trafic",
        "unite": "départs",
        "formule": "Nombre de navire arrivés en rade durant la période.",
    },
    {
        "code": "TRAFIC_NB_DEPARTS",
        "libelle": "Nombre de départs",
        "categorie": "trafic",
        "unite": "départs",
        "formule": "Nombre de navires ayant quitté le port durant la période."
    },
    # ---- KPI Temps ----
    {
        "code": "TEMPS_ATTENTE_MOYEN",
        "libelle": "Temps moyen d'attente",
        "categorie": "temps",
        "unite": "heures",
        "formule": "Moyenne de (date_accostage - date_arrivee) sur les escales accostées dans la période."
    },
    {
        "code": "TEMPS_SEJOUR_MOYEN",
        "libelle": "Temps moyen de sejour",
        "categorie": "temps",
        "unite": "heures",
        "formule": "Moyenne de (date_depart - date_arrivee) sur les escales parties dans la période.",
    },
    {
        "code": "TEMPS_PILOTAGE_MOYEN",
        "libelle": "Temps moyen de pilotage",
        "categorie": "temps",
        "unite": "heures",
        "formule": "Moyenne de la durrée cumulée pilote-à-bord (arrivée + départ) sur la période."
    },
    {
        "code": "TEMPS_ACCOSTAGE_MOYEN",
        "libelle": "Temps moyen d'accostage",
        "categorie": "temps",
        "unite": "heures",
        "formule": "Moyenne de la durée de la manoeuvre d'accostage (pilote à bord -> arrivée à quai).",
    },
    # ---- KPI Infrastructure ----
    {
        "code": "INFRA_TAUX_OCCUPATION",
        "libelle": "Taux d'occupation des quais",
        "categorie": "infrastructures",
        "unite": "%",
        "formule": "Somme des durées d'occupation à quai / (nombre de quais actifs x durée de la période) x 100.",
    },
    {
        "code": "INFRA_ROTATION_QUAIS",
        "libelle": "Rotation des quais",
        "categorie": "infrastructures",
        "unite": "escales/quai",
        "formule": "Nombre d'escales de la période / nombre de quais ayant reçu au moins une escale.",
    },
    {
        "code": "INFRA_DISPONIBILITE_POSTES",
        "libelle": "Disponibilité des postes",
        "categorie": "infrastructures",
        "unite": "%",
        "formule": "100 - taux d'occupation des quais.",
    },
    # ---- KPI Performance ----
    {
        "code": "PERF_PRODUCTIVITE",
        "libelle": "Ponctualité",
        "categorie": "performance",
        "unite": "tonnes/escale",
        "formule": "Somme (tonnage débarqué + tonnage embarqué) / nombre d'escales de la période.",
    },
    {
        "code": "PERF_PONCTUALITE",
        "libelle": "Ponctualité",
        "categorie": "performance",
        "unite": "%",
        "formule": "Part des escales dont le tepms d'attente est inférieur ou égal au seuil de ponctualité (24h).",
    },
    {
        "code": "PERF_CONGESTION",
        "libelle": "Congestion",
        "categorie": "performance",
        "unite": "%",
        "formule": "Part des escales dont le temps d'attente dépasse le seuil de congestion (48h).",
    },
]

SEUIL_PONCTUALITE_HEURES = 24
SEUIL_CONGESTION_HEURES = 48
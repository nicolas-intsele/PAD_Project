"""
Mapping du format réel du "Registre mensuel des escales" du PAD
(fichier COLLECTE_DE_DONNEES_NAVIRES_*.xlsx).

Ce format diffère du gabarit CSV/Excel générique utilisé par
apps.etl.importers.csv_importer / excel_importer : c'est un classeur unique
avec un onglet par mois, un double en-tête (groupe + champ), et deux tableaux
Excel juxtaposés par onglet (escales + mouvements internes au port).
"""

# Noms des 12 onglets mensuels tels qu'utilisés par le PAD (l'espace final
# après "DECEMBRE 2026" dans le fichier source est intentionnel).
ONGLETS_MOIS = [
    "JANVIER 2026", "FEVRIER 2026", "MARS 2026", "AVRIL 2026", "MAI 2026", "JUIN 2026",
    "JUILLET 2026", "AOUT 2026", "SEPTEMBRE 2026", "OCTOBRE 2026", "NOVEMBRE 2026", "DECEMBRE 2026 ",
]

ONGLET_NAVIRES = "DONNEES DES NAVIRES"
ONGLET_AUTRES = "AUTRES DONNEES"

# Les 42 premières colonnes (A:AP) de chaque onglet mensuel forment le
# tableau des escales, dans cet ordre positionnel constant. Les colonnes
# suivantes (AR:AW, "MOUVEMENT DANS LE PORT") appartiennent à un second
# tableau indépendant, sans lien ligne-à-ligne avec le premier — elles ne
# sont pas traitées par cette version de l'importeur (voir README ETL).
COLONNES_ESCALES = [
    "navire", "capitaine", "indicatif", "pavillon", "provenance", "armateur", "consignataire",
    "jauge_brute", "jauge_nette", "longueur", "largeur", "tirant_eau_franc_bord", "tonnage",
    "type_navire", "nombre_equipage", "nombre_passager", "type_navigation", "type_exploitation",
    "cargaison",
    "tirant_avant_arrivee", "tirant_arriere_arrivee", "arrivee_rade",
    "pilote_a_bord_arrivee", "nom_pilote_arrivee", "arrivee_poste", "poste",
    "tonnage_debarque", "pilote_debarque_arrivee",
    "deplacement_inutile_arrivee_01", "deplacement_inutile_arrivee_02", "stand_by_pilote",
    "etd", "destination", "tonnage_embarque", "tirant_avant_depart", "tirant_arriere_depart",
    "pilote_a_bord_depart", "nom_pilote_depart", "navire_appareille", "pilote_debarque_depart",
    "deplacement_inutile_depart_01", "deplacement_inutile_depart_02",
]
NB_COLONNES_ESCALES = len(COLONNES_ESCALES)  # 42, positions 0..41 dans chaque onglet mensuel

COLONNES_DATE_ESCALES = [
    "arrivee_rade", "pilote_a_bord_arrivee", "arrivee_poste", "pilote_debarque_arrivee",
    "etd", "pilote_a_bord_depart", "navire_appareille", "pilote_debarque_depart",
]

COLONNES_REQUISES_ESCALES = ["navire", "poste", "arrivee_rade"]

COLONNES_NAVIRES_REF = [
    "navire", "capitaine", "indicatif", "pavillon", "type_navire", "imo",
    "longueur", "largeur", "armateur", "jauge_brute", "jauge_nette",
]

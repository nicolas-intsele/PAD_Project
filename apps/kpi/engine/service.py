"""
Orchestration du calcul des KPI : garantit le catalogue, calcule chaque
indicateur pour une période mensuelle, et historise le résultat dans
ValeurKPI (une ligne par couple KPI x mois, datée au 1er jour du mois).
"""
from __future__ import annotations

import calendar
import logging
from datetime import date

from apps.referentiel.models import Calendrier

from ..catalogue import CATALOGUE_KPI
from ..models import KPI, ValeurKPI
from .calculateurs import CALCULATEURS

logger = logging.getLogger(__name__)


def garantir_catalogue() -> None:
    """Crée ou met à jour les 13 KPI définis dans le cahier des charges (idempotent)."""
    for entree in CATALOGUE_KPI:
        KPI.objects.update_or_create(
            code=entree["code"],
            defaults={
                "libelle": entree["libelle"],
                "categorie": entree["categorie"],
                "unite": entree["unite"],
                "formule": entree["formule"],
            },
        )


def calculer_kpi_mois(annee: int, mois: int) -> dict:
    """
    Calcule et historise les 13 KPI pour le mois donné.
    Retourne un dict {code_kpi: valeur} pour inspection/affichage.
    """
    garantir_catalogue()

    date_debut = date(annee, mois, 1)
    dernier_jour = calendar.monthrange(annee, mois)[1]
    date_fin = date(annee, mois, dernier_jour)
    date_ref = Calendrier.get_or_create_from_date(date_debut)

    resultats = {}
    for code, fonction in CALCULATEURS.items():
        valeur = fonction(date_debut, date_fin)
        if valeur is not None:
            kpi = KPI.objects.get(code=code)
            ValeurKPI.objects.update_or_create(
                kpi=kpi, date_ref=date_ref, defaults={"valeur": valeur}
            )
        resultats[code] = valeur

    logger.info("KPI calculés pour %s-%02d : %s", annee, mois, resultats)
    return resultats


def mois_disponibles() -> list[tuple[int, int]]:
    """Liste les couples (année, mois) distincts présents dans la table ESCALE."""
    from apps.escales.models import Escale

    dates = (
        Escale.objects.dates("date_arrivee", "month")
    )
    return sorted({(d.year, d.month) for d in dates})


def calculer_toutes_les_periodes() -> dict:
    """Recalcule les KPI pour tous les mois où au moins une escale existe."""
    resultats_par_mois = {}
    for annee, mois in mois_disponibles():
        resultats_par_mois[f"{annee}-{mois:02d}"] = calculer_kpi_mois(annee, mois)
    return resultats_par_mois
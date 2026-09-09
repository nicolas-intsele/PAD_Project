"""
Orchestration du calcul des KPI.

Les calculateurs reçoivent maintenant (annee, mois) et filtrent par
mois_source plutôt que par date_arrivee (Option B PAD).
"""
from __future__ import annotations

import logging
from datetime import date

from apps.referentiel.models import Calendrier

from ..catalogue import CATALOGUE_KPI
from ..models import KPI, ValeurKPI
from .calculateurs import CALCULATEURS

logger = logging.getLogger(__name__)


def garantir_catalogue() -> None:
    """Crée ou met à jour les KPI définis dans le catalogue (idempotent)."""
    for entree in CATALOGUE_KPI:
        KPI.objects.update_or_create(
            code=entree["code"],
            defaults={
                "libelle":   entree["libelle"],
                "categorie": entree["categorie"],
                "unite":     entree["unite"],
                "formule":   entree["formule"],
            },
        )


def calculer_kpi_mois(annee: int, mois: int) -> dict:
    """
    Calcule et historise les 11 KPI actifs pour le mois donné.
    Les calculateurs filtrent par mois_source="{annee}-{mois:02d}".
    Retourne un dict {code_kpi: valeur} pour affichage.
    """
    garantir_catalogue()

    date_debut = date(annee, mois, 1)
    date_ref = Calendrier.get_or_create_from_date(date_debut)

    resultats = {}
    for code, fonction in CALCULATEURS.items():
        try:
            valeur = fonction(annee, mois)
        except Exception as exc:
            logger.warning("KPI %s erreur : %s", code, exc)
            valeur = None

        if valeur is not None:
            kpi = KPI.objects.get(code=code)
            ValeurKPI.objects.update_or_create(
                kpi=kpi, date_ref=date_ref, defaults={"valeur": valeur}
            )
        resultats[code] = valeur

    logger.info("KPI calculés pour %s-%02d : %s", annee, mois, resultats)
    return resultats


def mois_disponibles() -> list[tuple[int, int]]:
    """Liste les couples (année, mois) distincts présents via mois_source."""
    from apps.escales.models import Escale
    cles = Escale.objects.exclude(
        mois_source__isnull=True
    ).values_list("mois_source", flat=True).distinct()
    result = set()
    for cle in cles:
        try:
            annee, mois = int(cle[:4]), int(cle[5:7])
            result.add((annee, mois))
        except (ValueError, TypeError, IndexError):
            pass
    return sorted(result)


def calculer_toutes_les_periodes() -> dict:
    """Recalcule les KPI pour tous les mois où au moins une escale existe."""
    resultats_par_mois = {}
    for annee, mois in mois_disponibles():
        resultats_par_mois[f"{annee}-{mois:02d}"] = calculer_kpi_mois(annee, mois)
    return resultats_par_mois

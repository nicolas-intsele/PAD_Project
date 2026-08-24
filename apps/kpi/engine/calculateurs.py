"""
Moteur de calcul des KPI.

Chaque fonction calcule un indicateur sur une période [date_debut, date_fin]
(bornes incluses) à partir de la table de faits ESCALE, et retourne une
valeur numérique (ou None si non calculable faute de données).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Avg, Sum

from apps.escales.models import Escale
from apps.referentiel.models import Quai

from ..catalogue import SEUIL_CONGESTION_HEURES, SEUIL_PONCTUALITE_HEURES


def _arrondir(valeur, decimales=3):
    if valeur is None:
        return None
    return round(Decimal(valeur), decimales)


# --------------------------------------------------------------------------
# KPI Trafic
# --------------------------------------------------------------------------

def nombre_escales(date_debut: date, date_fin: date) -> Decimal:
    n = Escale.objects.filter(date_arrivee__date__range=(date_debut, date_fin)).count()
    return Decimal(n)


def nombre_arrivees(date_debut: date, date_fin: date) -> Decimal:
    # Identique à nombre_escales dans ce modèle (une escale = une arrivée),
    # conservé comme KPI distinct pour se conformer au cahier des charges.
    return nombre_escales(date_debut, date_fin)


def nombre_departs(date_debut: date, date_fin: date) -> Decimal:
    n = Escale.objects.filter(date_depart__date__range=(date_debut, date_fin)).count()
    return Decimal(n)


# --------------------------------------------------------------------------
# KPI Temps
# --------------------------------------------------------------------------

def temps_attente_moyen(date_debut: date, date_fin: date):
    qs = Escale.objects.filter(
        date_accostage__date__range=(date_debut, date_fin), temps_attente__isnull=False
    )
    moyenne = qs.aggregate(m=Avg("temps_attente"))["m"]
    return _arrondir(moyenne, 2)


def temps_sejour_moyen(date_debut: date, date_fin: date):
    qs = Escale.objects.filter(
        date_depart__date__range=(date_debut, date_fin), temps_sejour__isnull=False
    )
    moyenne = qs.aggregate(m=Avg("temps_sejour"))["m"]
    return _arrondir(moyenne, 2)


def temps_pilotage_moyen(date_debut: date, date_fin: date):
    qs = Escale.objects.filter(
        date_arrivee__date__range=(date_debut, date_fin), temps_pilotage__isnull=False
    )
    moyenne = qs.aggregate(m=Avg("temps_pilotage"))["m"]
    return _arrondir(moyenne, 2)


def temps_accostage_moyen(date_debut: date, date_fin: date):
    qs = Escale.objects.filter(
        date_arrivee__date__range=(date_debut, date_fin), temps_accostage__isnull=False
    )
    moyenne = qs.aggregate(m=Avg("temps_accostage"))["m"]
    return _arrondir(moyenne, 2)


# --------------------------------------------------------------------------
# KPI Infrastructures
# --------------------------------------------------------------------------

def _duree_periode_heures(date_debut: date, date_fin: date) -> float:
    nb_jours = (date_fin - date_debut).days + 1
    return nb_jours * 24


def taux_occupation_quais(date_debut: date, date_fin: date):
    """
    Somme des durées réelles d'occupation à quai (accostage -> appareillage,
    et non le temps de séjour total qui inclut l'attente en rade) des escales
    de la période, rapportée à la capacité théorique totale (nombre de quais
    référencés x durée de la période).
    """
    nb_quais = Quai.objects.count()
    if nb_quais == 0:
        return None

    qs = Escale.objects.filter(
        date_accostage__date__range=(date_debut, date_fin),
        date_accostage__isnull=False,
        date_appareillage__isnull=False,
    ).values_list("date_accostage", "date_appareillage")

    occupation_totale_heures = sum(
        max((appareillage - accostage).total_seconds() / 3600, 0)
        for accostage, appareillage in qs
    )

    capacite_totale = nb_quais * _duree_periode_heures(date_debut, date_fin)
    if capacite_totale == 0:
        return None
    taux = (occupation_totale_heures / capacite_totale) * 100
    return _arrondir(min(taux, 100), 2)


def rotation_quais(date_debut: date, date_fin: date):
    nb_quais_actifs = (
        Escale.objects.filter(date_arrivee__date__range=(date_debut, date_fin))
        .values("quai").distinct().count()
    )
    if nb_quais_actifs == 0:
        return None
    n = nombre_escales(date_debut, date_fin)
    return _arrondir(float(n) / nb_quais_actifs, 2)


def disponibilite_postes(date_debut: date, date_fin: date):
    taux = taux_occupation_quais(date_debut, date_fin)
    if taux is None:
        return None
    return _arrondir(100 - float(taux), 2)


# --------------------------------------------------------------------------
# KPI Performance
# --------------------------------------------------------------------------

def productivite(date_debut: date, date_fin: date):
    qs = Escale.objects.filter(date_arrivee__date__range=(date_debut, date_fin))
    n = qs.count()
    if n == 0:
        return None
    tonnage = qs.aggregate(
        t=Sum("tonnage_debarque"), e=Sum("tonnage_embarque")
    )
    total = (tonnage["t"] or 0) + (tonnage["e"] or 0)
    if total == 0:
        return None
    return _arrondir(float(total) / n, 2)


def ponctualite(date_debut: date, date_fin: date):
    qs = Escale.objects.filter(
        date_accostage__date__range=(date_debut, date_fin), temps_attente__isnull=False
    )
    total = qs.count()
    if total == 0:
        return None
    ponctuelles = qs.filter(temps_attente__lte=SEUIL_PONCTUALITE_HEURES).count()
    return _arrondir((ponctuelles / total) * 100, 2)


def congestion(date_debut: date, date_fin: date):
    qs = Escale.objects.filter(
        date_accostage__date__range=(date_debut, date_fin), temps_attente__isnull=False
    )
    total = qs.count()
    if total == 0:
        return None
    en_congestion = qs.filter(temps_attente__gt=SEUIL_CONGESTION_HEURES).count()
    return _arrondir((en_congestion / total) * 100, 2)


# --------------------------------------------------------------------------
# Registre des calculateurs, indexé par code KPI
# --------------------------------------------------------------------------

CALCULATEURS = {
    "TRAFIC_NB_ESCALES": nombre_escales,
    "TRAFIC_NB_ARRIVEES": nombre_arrivees,
    "TRAFIC_NB_DEPARTS": nombre_departs,
    "TEMPS_ATTENTE_MOYEN": temps_attente_moyen,
    "TEMPS_SEJOUR_MOYEN": temps_sejour_moyen,
    "TEMPS_PILOTAGE_MOYEN": temps_pilotage_moyen,
    "TEMPS_ACCOSTAGE_MOYEN": temps_accostage_moyen,
    "INFRA_TAUX_OCCUPATION": taux_occupation_quais,
    "INFRA_ROTATION_QUAIS": rotation_quais,
    "INFRA_DISPONIBILITE_POSTES": disponibilite_postes,
    "PERF_PRODUCTIVITE": productivite,
    "PERF_PONCTUALITE": ponctualite,
    "PERF_CONGESTION": congestion,
}
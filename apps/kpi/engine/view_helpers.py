"""
Adaptateurs pour les vues dashboard.

Les calculateurs de KPI fonctionnent par (annee, mois) via mois_source.
Ces fonctions adaptent les appels depuis les vues qui travaillent avec
des plages de dates libres, en agrégeant sur tous les mois couverts.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from .calculateurs import (
    nombre_escales, nombre_arrivees, nombre_departs,
    temps_attente_moyen, temps_sejour_moyen,
    temps_pilotage_moyen, temps_accostage_moyen,
    taux_occupation_postes, rotation_postes,
    productivite, debit_postes,
)


def _mois_dans_plage(date_debut: date, date_fin: date) -> list[tuple[int, int]]:
    """Retourne la liste des (annee, mois) couverts par la plage."""
    mois = []
    annee, mois_num = date_debut.year, date_debut.month
    while (annee, mois_num) <= (date_fin.year, date_fin.month):
        mois.append((annee, mois_num))
        mois_num += 1
        if mois_num > 12:
            mois_num = 1
            annee += 1
    return mois


def _somme_ponderee(fn, date_debut: date, date_fin: date,
                    fn_poids=None) -> Optional[Decimal]:
    """
    Calcule la moyenne pondérée d'un indicateur sur une plage de dates.
    fn_poids : fonction (annee, mois) → nombre de lignes (pour pondération).
               Si None, moyenne simple.
    """
    mois = _mois_dans_plage(date_debut, date_fin)
    valeurs, poids_list = [], []

    for annee, mois_num in mois:
        v = fn(annee, mois_num)
        if v is None:
            continue
        if fn_poids:
            p = float(fn_poids(annee, mois_num) or 1)
            valeurs.append(float(v) * p)
            poids_list.append(p)
        else:
            valeurs.append(float(v))

    if not valeurs:
        return None

    if fn_poids and poids_list:
        total_poids = sum(poids_list)
        return Decimal(str(round(sum(valeurs) / total_poids, 2))) if total_poids else None
    return Decimal(str(round(sum(valeurs) / len(valeurs), 2)))


def _somme(fn, date_debut: date, date_fin: date) -> Optional[Decimal]:
    """Somme d'un indicateur de comptage sur la plage."""
    mois = _mois_dans_plage(date_debut, date_fin)
    total = Decimal(0)
    for annee, mois_num in mois:
        v = fn(annee, mois_num)
        if v is not None:
            total += v
    return total


# Wrappers appelables avec (date_debut, date_fin) depuis les vues

def nb_escales_plage(d1, d2):
    return _somme(nombre_escales, d1, d2)

def nb_arrivees_plage(d1, d2):
    return _somme(nombre_arrivees, d1, d2)

def nb_departs_plage(d1, d2):
    return _somme(nombre_departs, d1, d2)

def attente_plage(d1, d2):
    return _somme_ponderee(temps_attente_moyen, d1, d2, nombre_escales)

def sejour_plage(d1, d2):
    return _somme_ponderee(temps_sejour_moyen, d1, d2, nombre_arrivees)

def pilotage_plage(d1, d2):
    return _somme_ponderee(temps_pilotage_moyen, d1, d2, nombre_arrivees)

def accostage_plage(d1, d2):
    return _somme_ponderee(temps_accostage_moyen, d1, d2, nombre_arrivees)

def occupation_plage(d1, d2):
    return _somme_ponderee(taux_occupation_postes, d1, d2)

def rotation_plage(d1, d2):
    return _somme_ponderee(rotation_postes, d1, d2)

def productivite_plage(d1, d2):
    return _somme_ponderee(productivite, d1, d2, nombre_arrivees)

def debit_plage(d1, d2):
    return _somme_ponderee(debit_postes, d1, d2)

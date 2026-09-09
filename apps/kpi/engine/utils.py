"""
Utilitaires partagés du moteur de calcul.

Ce module centralise les fonctions de calcul utilisées à la fois par
apps.kpi.engine.calculateurs et apps.analytics.cube, évitant la duplication
identifiée lors de l'audit (MO3 — Phase 7).
"""
from datetime import date


def duree_periode_heures(date_debut: date, date_fin: date) -> float:
    """Retourne le nombre d'heures dans la période [date_debut, date_fin] (bornes incluses)."""
    return ((date_fin - date_debut).days + 1) * 24

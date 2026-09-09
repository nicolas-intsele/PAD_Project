"""
Mapping entre les codes d'axes d'analyse et les annotations/groupements ORM.

Chaque entrée du registre AXES_CONFIG décrit comment transformer un
queryset Escale pour regrouper selon cet axe :
  - annotate  : dict d'annotations Django à ajouter au queryset
  - group_by  : nom du champ (annoté ou FK-traversé) à passer à values()
  - label_fn  : callable(row_dict) → str  pour fabriquer le libellé affiché
"""
from __future__ import annotations

from django.db.models import CharField, F, Value
from django.db.models.functions import (
    Cast,
    Concat,
    ExtractMonth,
    ExtractQuarter,
    ExtractYear,
)

from .models import AxeAnalyse

# --------------------------------------------------------------------------
# Helpers de fabrication de libellé
# --------------------------------------------------------------------------

def _label_mois(row: dict) -> str:
    mois_noms = [
        "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
    ]
    try:
        annee = int(row.get("_annee", row.get("_groupe", 0)))
        mois = int(row.get("_mois", 0))
        return f"{mois_noms[mois]} {annee}"
    except (ValueError, IndexError):
        return str(row.get("_groupe", ""))


def _label_trimestre(row: dict) -> str:
    try:
        annee = int(row.get("_annee", 0))
        trim = int(row.get("_trimestre", 0))
        return f"T{trim} {annee}"
    except ValueError:
        return str(row.get("_groupe", ""))


def _label_annee(row: dict) -> str:
    return str(row.get("_groupe", ""))


def _label_simple(key: str):
    """Fabrique un label_fn qui retourne simplement row[key]."""
    def fn(row: dict) -> str:
        return str(row.get(key, ""))
    return fn


# --------------------------------------------------------------------------
# Registre central
# --------------------------------------------------------------------------

AXES_CONFIG: dict[str, dict] = {
    AxeAnalyse.Type.TEMPS_MOIS: {
        "annotate": {
            "_annee": ExtractYear("date_arrivee"),
            "_mois": ExtractMonth("date_arrivee"),
            # clé de tri naturelle (ex. "2026-03") — utilisée aussi comme group_by
            "_groupe": Concat(
                Cast(ExtractYear("date_arrivee"), output_field=CharField()),
                Value("-"),
                Cast(ExtractMonth("date_arrivee"), output_field=CharField()),
                output_field=CharField(),
            ),
        },
        "group_by": ["_groupe", "_annee", "_mois"],
        "order_by": ["_annee", "_mois"],
        "label_fn": _label_mois,
    },
    AxeAnalyse.Type.TEMPS_TRIMESTRE: {
        "annotate": {
            "_annee": ExtractYear("date_arrivee"),
            "_trimestre": ExtractQuarter("date_arrivee"),
            "_groupe": Concat(
                Cast(ExtractYear("date_arrivee"), output_field=CharField()),
                Value("-T"),
                Cast(ExtractQuarter("date_arrivee"), output_field=CharField()),
                output_field=CharField(),
            ),
        },
        "group_by": ["_groupe", "_annee", "_trimestre"],
        "order_by": ["_annee", "_trimestre"],
        "label_fn": _label_trimestre,
    },
    AxeAnalyse.Type.TEMPS_ANNEE: {
        "annotate": {
            "_groupe": Cast(ExtractYear("date_arrivee"), output_field=CharField()),
        },
        "group_by": ["_groupe"],
        "order_by": ["_groupe"],
        "label_fn": _label_annee,
    },
    AxeAnalyse.Type.TERMINAL: {
        "annotate": {"_groupe": F("poste__terminal__nom")},
        "group_by": ["_groupe"],
        "order_by": ["_groupe"],
        "label_fn": _label_simple("_groupe"),
    },
    AxeAnalyse.Type.POSTE: {
        "annotate": {"_groupe": F("poste__nom")},
        "group_by": ["_groupe"],
        "order_by": ["_groupe"],
        "label_fn": _label_simple("_groupe"),
    },
    AxeAnalyse.Type.TYPE_NAVIRE: {
        "annotate": {"_groupe": F("navire__type_navire__libelle")},
        "group_by": ["_groupe"],
        "order_by": ["_groupe"],
        "label_fn": _label_simple("_groupe"),
    },
    AxeAnalyse.Type.COMPAGNIE: {
        "annotate": {"_groupe": F("navire__compagnie__raison_sociale")},
        "group_by": ["_groupe"],
        "order_by": ["_groupe"],
        "label_fn": _label_simple("_groupe"),
    },
    AxeAnalyse.Type.AGENT: {
        "annotate": {"_groupe": F("agent__nom")},
        "group_by": ["_groupe"],
        "order_by": ["_groupe"],
        "label_fn": _label_simple("_groupe"),
    },
    AxeAnalyse.Type.STATUT: {
        "annotate": {"_groupe": F("statut")},
        "group_by": ["_groupe"],
        "order_by": ["_groupe"],
        "label_fn": _label_simple("_groupe"),
    },
}

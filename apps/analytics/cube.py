"""
Moteur de calcul multidimensionnel (Module 4).

Point d'entrée : ``MoteurCube``.
Il prend :
  - une mesure (ex. "nb_escales")
  - un axe de ligne (ex. "terminal")
  - un axe de colonne optionnel (ex. "temps_mois")
  - une période de filtrage (date_debut / date_fin)

Et produit :
  - une liste de dicts (format "plat" pour l'API)
  - un tableau croisé (format pivot pour les dashboards)
"""
from __future__ import annotations

import calendar
import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, Q, Sum

from apps.escales.models import Escale
from apps.referentiel.models import Poste

from .dimensions import AXES_CONFIG
from .models import AxeAnalyse, CubeAnalyse

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _arrondir(val, d: int = 2) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val), d)
    except (TypeError, ValueError):
        return None


def _duree_periode_heures(date_debut: date, date_fin: date) -> float:
    # MO3 (audit Phase 7) : délégué au module utilitaire partagé kpi.engine.utils
    # pour éviter la duplication avec apps.kpi.engine.calculateurs.
    from apps.kpi.engine.utils import duree_periode_heures
    return duree_periode_heures(date_debut, date_fin)


# --------------------------------------------------------------------------
# Fonctions d'agrégation par mesure
# --------------------------------------------------------------------------

def _agréger(qs, mesure: str, date_debut: date, date_fin: date) -> dict[str, Any]:
    """
    Applique l'agrégation correspondant à la mesure sur un queryset déjà filtré/groupé.
    Retourne un dict {clé_groupe: valeur} pour chaque groupe.
    """
    if mesure == CubeAnalyse.Mesure.NB_ESCALES:
        return {"valeur": qs.count()}

    if mesure == CubeAnalyse.Mesure.NB_ARRIVEES:
        return {"valeur": qs.filter(date_arrivee__isnull=False).count()}

    if mesure == CubeAnalyse.Mesure.NB_DEPARTS:
        return {"valeur": qs.filter(date_depart__isnull=False).count()}

    if mesure == CubeAnalyse.Mesure.TEMPS_ATTENTE_MOY:
        agg = qs.filter(temps_attente__isnull=False).aggregate(v=Avg("temps_attente"))
        return {"valeur": _arrondir(agg["v"])}

    if mesure == CubeAnalyse.Mesure.TEMPS_SEJOUR_MOY:
        agg = qs.filter(temps_sejour__isnull=False).aggregate(v=Avg("temps_sejour"))
        return {"valeur": _arrondir(agg["v"])}

    if mesure == CubeAnalyse.Mesure.TEMPS_PILOTAGE_MOY:
        agg = qs.filter(temps_pilotage__isnull=False).aggregate(v=Avg("temps_pilotage"))
        return {"valeur": _arrondir(agg["v"])}

    if mesure == CubeAnalyse.Mesure.TAUX_OCCUPATION:
        nb_postes = Poste.objects.count()
        if nb_postes == 0:
            return {"valeur": None}
        paires = qs.filter(
            date_accostage__isnull=False,
            date_appareillage__isnull=False,
        ).values_list("date_accostage", "date_appareillage")
        occ = sum(
            max((app - acc).total_seconds() / 3600, 0) for acc, app in paires
        )
        cap = nb_postes * _duree_periode_heures(date_debut, date_fin)
        return {"valeur": _arrondir(min(occ / cap * 100, 100) if cap else None)}

    if mesure == CubeAnalyse.Mesure.TONNAGE_TOTAL:
        agg = qs.aggregate(d=Sum("tonnage_debarque"), e=Sum("tonnage_embarque"))
        total = (agg["d"] or 0) + (agg["e"] or 0)
        return {"valeur": _arrondir(total) if total else None}

    if mesure == CubeAnalyse.Mesure.PRODUCTIVITE:
        n = qs.count()
        if n == 0:
            return {"valeur": None}
        agg = qs.aggregate(d=Sum("tonnage_debarque"), e=Sum("tonnage_embarque"))
        total = (agg["d"] or 0) + (agg["e"] or 0)
        return {"valeur": _arrondir(float(total) / n) if total else None}

    if mesure == CubeAnalyse.Mesure.TAUX_PONCTUALITE:
        n = qs.filter(temps_attente__isnull=False).count()
        if n == 0:
            return {"valeur": None}
        ponctuels = qs.filter(temps_attente__lte=24).count()
        return {"valeur": _arrondir(ponctuels / n * 100)}

    if mesure == CubeAnalyse.Mesure.TAUX_CONGESTION:
        n = qs.filter(temps_attente__isnull=False).count()
        if n == 0:
            return {"valeur": None}
        congestion = qs.filter(temps_attente__gt=48).count()
        return {"valeur": _arrondir(congestion / n * 100)}

    return {"valeur": None}


# --------------------------------------------------------------------------
# Moteur principal
# --------------------------------------------------------------------------

class MoteurCube:
    """
    Calcule un cube OLAP 1D ou 2D pour une mesure donnée et une période.

    Usage ::

        moteur = MoteurCube(
            mesure="nb_escales",
            axe_ligne="terminal",
            axe_colonne="temps_mois",   # optionnel
            date_debut=date(2026, 1, 1),
            date_fin=date(2026, 6, 30),
        )
        plat    = moteur.calculer_plat()      # liste de dicts
        pivot   = moteur.calculer_pivot()     # {ligne: {colonne: valeur}}
        resume  = moteur.calculer_resume()    # totaux + statistiques globales
    """

    def __init__(
        self,
        mesure: str,
        axe_ligne: str,
        axe_colonne: str | None = None,
        date_debut: date | None = None,
        date_fin: date | None = None,
    ):
        self.mesure = mesure
        self.axe_ligne = axe_ligne
        self.axe_colonne = axe_colonne
        self.date_debut = date_debut or date(2020, 1, 1)
        self.date_fin = date_fin or date.today()

        # Validation
        if axe_ligne not in AXES_CONFIG:
            raise ValueError(f"Axe ligne inconnu : {axe_ligne}")
        if axe_colonne and axe_colonne not in AXES_CONFIG:
            raise ValueError(f"Axe colonne inconnu : {axe_colonne}")
        if axe_colonne and axe_colonne == axe_ligne:
            raise ValueError("L'axe ligne et l'axe colonne doivent être différents.")

    # ------------------------------------------------------------------
    def _qs_base(self) -> "QuerySet":
        """Queryset de base filtré sur la période."""
        return Escale.objects.filter(
            date_arrivee__date__range=(self.date_debut, self.date_fin)
        ).select_related(
            "navire__type_navire",
            "navire__compagnie",
            "poste__terminal",
            "agent",
        )

    def _appliquer_axe(self, qs, config: dict) -> "QuerySet":
        """Annote et regroupe le queryset selon la config d'un axe."""
        qs = qs.annotate(**config["annotate"])
        qs = qs.values(*config["group_by"])
        return qs

    # ------------------------------------------------------------------
    def calculer_plat(self) -> list[dict]:
        """
        Résultat 1D : liste de dicts
        [{"ligne": "Terminal A", "valeur": 42}, ...]
        Si axe_colonne défini : liste 2D avec clé "colonne" supplémentaire.
        """
        cfg_ligne = AXES_CONFIG[self.axe_ligne]

        if self.axe_colonne is None:
            return self._calculer_1d(cfg_ligne)
        else:
            return self._calculer_2d(cfg_ligne, AXES_CONFIG[self.axe_colonne])

    def _calculer_1d(self, cfg_ligne: dict) -> list[dict]:
        qs = self._qs_base()
        qs = qs.annotate(**cfg_ligne["annotate"])
        groupes = qs.values(*cfg_ligne["group_by"]).order_by(
            *cfg_ligne.get("order_by", ["_groupe"])
        ).distinct()

        resultats = []
        for row in groupes:
            groupe_val = row.get("_groupe")
            if groupe_val is None:
                continue
            qs_groupe = qs.filter(**{k: v for k, v in row.items()})
            agg = _agréger(qs_groupe, self.mesure, self.date_debut, self.date_fin)
            resultats.append({
                "groupe": groupe_val,
                "label": cfg_ligne["label_fn"](row),
                "valeur": agg["valeur"],
                **{k: v for k, v in row.items() if k not in ("_groupe",)},
            })
        return resultats

    def _calculer_2d(self, cfg_ligne: dict, cfg_col: dict) -> list[dict]:
        """Résultat 2D : liste de dicts {ligne, colonne, label_ligne, label_colonne, valeur}."""
        qs = self._qs_base()
        # Annoter avec les deux axes
        annotations = {**cfg_ligne["annotate"], **cfg_col["annotate"]}
        # Renommer les annotations de colonne pour éviter les conflits
        col_annotations = {}
        for k, v in cfg_col["annotate"].items():
            col_annotations[f"_col{k}"] = v
        annotations = {**cfg_ligne["annotate"], **col_annotations}
        qs = qs.annotate(**annotations)

        # Groupes ligne
        group_by_ligne = cfg_ligne["group_by"]
        group_by_col = [f"_col{k}" for k in cfg_col["group_by"]]

        groupes = (
            qs.values(*(group_by_ligne + group_by_col))
            .order_by(
                *cfg_ligne.get("order_by", ["_groupe"]),
                *[f"_col{k}" for k in cfg_col.get("order_by", ["_groupe"])],
            )
            .distinct()
        )

        resultats = []
        for row in groupes:
            val_ligne = row.get("_groupe")
            val_col = row.get("_col_groupe")
            if val_ligne is None or val_col is None:
                continue

            # Reconstituer les dicts de filtre pour chaque axe
            filtre_ligne = {k: row[k] for k in group_by_ligne}
            filtre_col = {f"_col{k}": row[f"_col{k}"] for k in cfg_col["group_by"]}
            qs_cellule = qs.filter(**filtre_ligne, **filtre_col)

            agg = _agréger(qs_cellule, self.mesure, self.date_debut, self.date_fin)

            # Reconstituer les dicts "propres" pour les label_fn
            row_ligne = {k.replace("_col", ""): row[k] for k in group_by_ligne}
            row_col = {k.replace("_col", ""): row[f"_col{k}"] for k in cfg_col["group_by"]}

            resultats.append({
                "ligne": val_ligne,
                "label_ligne": cfg_ligne["label_fn"](row_ligne),
                "colonne": val_col,
                "label_colonne": cfg_col["label_fn"](row_col),
                "valeur": agg["valeur"],
            })
        return resultats

    # ------------------------------------------------------------------
    def calculer_pivot(self) -> dict:
        """
        Retourne un tableau croisé :
        {
          "lignes": ["Terminal A", "Terminal B", ...],
          "colonnes": ["2026-1", "2026-2", ...],
          "labels_lignes": [...],
          "labels_colonnes": [...],
          "matrice": [[v11, v12], [v21, v22], ...]   (None si absent)
        }
        Disponible uniquement en mode 2D.
        """
        if not self.axe_colonne:
            raise ValueError("calculer_pivot() nécessite un axe_colonne.")

        donnees_2d = self.calculer_plat()

        lignes_set: dict[str, str] = {}   # groupe → label
        colonnes_set: dict[str, str] = {}
        cellules: dict[tuple, Any] = {}

        for row in donnees_2d:
            l, c = row["ligne"], row["colonne"]
            lignes_set[l] = row["label_ligne"]
            colonnes_set[c] = row["label_colonne"]
            cellules[(l, c)] = row["valeur"]

        lignes = list(lignes_set.keys())
        colonnes = list(colonnes_set.keys())

        matrice = [
            [cellules.get((l, c)) for c in colonnes]
            for l in lignes
        ]

        return {
            "lignes": lignes,
            "labels_lignes": [lignes_set[l] for l in lignes],
            "colonnes": colonnes,
            "labels_colonnes": [colonnes_set[c] for c in colonnes],
            "matrice": matrice,
        }

    # ------------------------------------------------------------------
    def calculer_resume(self) -> dict:
        """
        Statistiques globales sur la période :
        total, moyenne, min, max, nb_groupes avec données.
        """
        donnees = self.calculer_plat()
        valeurs = [r["valeur"] for r in donnees if r.get("valeur") is not None]

        if not valeurs:
            return {
                "total": None, "moyenne": None, "minimum": None,
                "maximum": None, "nb_groupes": 0, "nb_avec_donnees": 0,
            }

        return {
            "total": _arrondir(sum(valeurs)),
            "moyenne": _arrondir(sum(valeurs) / len(valeurs)),
            "minimum": _arrondir(min(valeurs)),
            "maximum": _arrondir(max(valeurs)),
            "nb_groupes": len(donnees),
            "nb_avec_donnees": len(valeurs),
        }

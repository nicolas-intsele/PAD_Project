"""
Analyses avancées du Module 4 — au-delà du simple cube OLAP :

  - TendanceTemporelle  : évolution d'une mesure mois par mois + droite de régression
  - ComparaisonPeriodes : delta et variation % entre deux périodes
  - ClassementEntites   : top-N / bottom-N par mesure sur une période
  - AnalyseCorrelation  : corrélation entre deux mesures sur la même série temporelle
  - RepartitionStatut   : distribution des escales par statut sur une période
  - HeatmapOccupation   : taux d'occupation des quais par semaine/jour
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.db.models.functions import ExtractMonth, ExtractWeek, ExtractYear

from apps.escales.models import Escale
from apps.referentiel.models import Poste

logger = logging.getLogger(__name__)


def _arrondir(val, d: int = 3) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val), d)
    except (TypeError, ValueError):
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 1. Tendance temporelle avec régression linéaire
# ──────────────────────────────────────────────────────────────────────────────

def calculer_tendance(
    mesure: str,
    date_debut: date,
    date_fin: date,
    granularite: str = "mois",        # "mois" | "trimestre" | "annee"
) -> dict:
    """
    Calcule l'évolution d'une mesure sur la période et y ajuste une régression
    linéaire (scipy.stats.linregress) pour détecter la tendance.

    Retourne ::

        {
          "serie": [
              {"periode": "2026-01", "label": "Janvier 2026", "valeur": 42.0},
              ...
          ],
          "regression": {
              "pente": 3.2,          # variation par période
              "ordonnee_origine": 35.0,
              "r_carre": 0.87,       # coefficient de détermination
              "tendance": "hausse"   # "hausse" | "baisse" | "stable"
          },
          "variation_totale": 18.0,  # dernière valeur - première valeur
          "variation_pct": 43.0,     # en %
        }
    """
    from .cube import MoteurCube

    axe_map = {"mois": "temps_mois", "trimestre": "temps_trimestre", "annee": "temps_annee"}
    axe = axe_map.get(granularite, "temps_mois")

    moteur = MoteurCube(
        mesure=mesure,
        axe_ligne=axe,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    serie_brute = moteur.calculer_plat()

    serie = [
        {
            "periode": row["groupe"],
            "label": row["label"],
            "valeur": row["valeur"],
        }
        for row in serie_brute
    ]

    valeurs = [s["valeur"] for s in serie if s["valeur"] is not None]
    regression = None
    variation_totale = None
    variation_pct = None

    if len(valeurs) >= 2:
        try:
            from scipy import stats as sp_stats

            x = list(range(len(valeurs)))
            slope, intercept, r_value, p_value, std_err = sp_stats.linregress(x, valeurs)
            r2 = r_value ** 2

            if abs(slope) < 0.01 * (max(valeurs) - min(valeurs) + 1e-9):
                tendance = "stable"
            elif slope > 0:
                tendance = "hausse"
            else:
                tendance = "baisse"

            regression = {
                "pente": _arrondir(slope),
                "ordonnee_origine": _arrondir(intercept),
                "r_carre": _arrondir(r2),
                "p_value": _arrondir(p_value, 4),
                "tendance": tendance,
                "valeurs_ajustees": [_arrondir(intercept + slope * i) for i in x],
            }
        except ImportError:
            logger.warning("scipy non disponible — régression désactivée")

        variation_totale = _arrondir(valeurs[-1] - valeurs[0])
        if valeurs[0] and valeurs[0] != 0:
            variation_pct = _arrondir((valeurs[-1] - valeurs[0]) / abs(valeurs[0]) * 100)

    return {
        "serie": serie,
        "regression": regression,
        "variation_totale": variation_totale,
        "variation_pct": variation_pct,
        "nb_periodes": len(serie),
        "nb_periodes_avec_donnees": len(valeurs),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 2. Comparaison de deux périodes
# ──────────────────────────────────────────────────────────────────────────────

def comparer_periodes(
    mesure: str,
    axe: str,
    periode_ref_debut: date,
    periode_ref_fin: date,
    periode_comp_debut: date,
    periode_comp_fin: date,
) -> list[dict]:
    """
    Compare les valeurs de la mesure par groupe (axe) entre deux périodes.

    Retourne une liste de dicts ::

        [
          {
            "groupe": "Terminal A",
            "label": "Terminal A",
            "valeur_ref": 120.0,
            "valeur_comp": 145.0,
            "delta": 25.0,
            "variation_pct": 20.83,
            "evolution": "hausse"
          },
          ...
        ]
    """
    from .cube import MoteurCube

    def _extraire(d_deb, d_fin):
        m = MoteurCube(mesure=mesure, axe_ligne=axe, date_debut=d_deb, date_fin=d_fin)
        return {row["groupe"]: row for row in m.calculer_plat()}

    ref_map = _extraire(periode_ref_debut, periode_ref_fin)
    comp_map = _extraire(periode_comp_debut, periode_comp_fin)

    tous_groupes = sorted(set(ref_map) | set(comp_map))
    resultats = []

    for groupe in tous_groupes:
        ref_row = ref_map.get(groupe, {})
        comp_row = comp_map.get(groupe, {})
        v_ref = ref_row.get("valeur")
        v_comp = comp_row.get("valeur")
        label = ref_row.get("label") or comp_row.get("label") or groupe

        delta = None
        variation_pct = None
        evolution = "nouveau" if v_ref is None else ("supprimé" if v_comp is None else "stable")

        if v_ref is not None and v_comp is not None:
            delta = _arrondir(v_comp - v_ref)
            if v_ref != 0:
                variation_pct = _arrondir((v_comp - v_ref) / abs(v_ref) * 100)
            evolution = "hausse" if (delta or 0) > 0 else ("baisse" if (delta or 0) < 0 else "stable")

        resultats.append({
            "groupe": groupe,
            "label": label,
            "valeur_ref": v_ref,
            "valeur_comp": v_comp,
            "delta": delta,
            "variation_pct": variation_pct,
            "evolution": evolution,
        })

    # tri par delta décroissant (les plus fortes hausses en tête)
    resultats.sort(key=lambda r: (r["delta"] or 0), reverse=True)
    return resultats


# ──────────────────────────────────────────────────────────────────────────────
# 3. Classement (top-N / bottom-N)
# ──────────────────────────────────────────────────────────────────────────────

def classement(
    mesure: str,
    axe: str,
    date_debut: date,
    date_fin: date,
    top: int = 10,
    ordre: str = "desc",   # "desc" = top performers, "asc" = pires
) -> list[dict]:
    """
    Retourne le top-N (ou bottom-N) des entités classées selon la mesure.
    Ajoute le rang et la part relative de chaque entité dans le total.
    """
    from .cube import MoteurCube

    moteur = MoteurCube(mesure=mesure, axe_ligne=axe, date_debut=date_debut, date_fin=date_fin)
    donnees = moteur.calculer_plat()

    avec_valeur = [r for r in donnees if r.get("valeur") is not None]
    sans_valeur = [r for r in donnees if r.get("valeur") is None]

    reverse = (ordre == "desc")
    tries = sorted(avec_valeur, key=lambda r: r["valeur"], reverse=reverse)[:top]

    total = sum(r["valeur"] for r in avec_valeur) or 1
    for rang, row in enumerate(tries, 1):
        row["rang"] = rang
        row["part_pct"] = _arrondir(row["valeur"] / total * 100)

    return tries


# ──────────────────────────────────────────────────────────────────────────────
# 4. Corrélation entre deux mesures
# ──────────────────────────────────────────────────────────────────────────────

def analyser_correlation(
    mesure_x: str,
    mesure_y: str,
    date_debut: date,
    date_fin: date,
    granularite: str = "mois",
) -> dict:
    """
    Calcule la corrélation de Pearson entre deux mesures sur la même série temporelle.

    Retourne ::

        {
          "points": [{"periode": ..., "x": ..., "y": ...}, ...],
          "correlation_pearson": 0.94,
          "interpretation": "forte corrélation positive"
        }
    """
    from .cube import MoteurCube

    axe_map = {"mois": "temps_mois", "trimestre": "temps_trimestre", "annee": "temps_annee"}
    axe = axe_map.get(granularite, "temps_mois")

    serie_x = {
        r["groupe"]: r["valeur"]
        for r in MoteurCube(mesure=mesure_x, axe_ligne=axe, date_debut=date_debut, date_fin=date_fin).calculer_plat()
    }
    serie_y = {
        r["groupe"]: r["valeur"]
        for r in MoteurCube(mesure=mesure_y, axe_ligne=axe, date_debut=date_debut, date_fin=date_fin).calculer_plat()
    }

    periodes_communes = sorted(set(serie_x) & set(serie_y))
    points = []
    vx, vy = [], []

    for p in periodes_communes:
        x, y = serie_x[p], serie_y[p]
        if x is not None and y is not None:
            points.append({"periode": p, "x": x, "y": y})
            vx.append(x)
            vy.append(y)

    correlation = None
    interpretation = "données insuffisantes"

    if len(vx) >= 3:
        try:
            from scipy.stats import pearsonr
            r, p = pearsonr(vx, vy)
            correlation = _arrondir(r, 3)
            if abs(r) >= 0.8:
                interpretation = "forte corrélation " + ("positive" if r > 0 else "négative")
            elif abs(r) >= 0.5:
                interpretation = "corrélation modérée " + ("positive" if r > 0 else "négative")
            elif abs(r) >= 0.2:
                interpretation = "faible corrélation " + ("positive" if r > 0 else "négative")
            else:
                interpretation = "pas de corrélation significative"
        except ImportError:
            pass

    return {
        "mesure_x": mesure_x,
        "mesure_y": mesure_y,
        "points": points,
        "correlation_pearson": correlation,
        "interpretation": interpretation,
        "nb_periodes": len(points),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 5. Répartition par statut
# ──────────────────────────────────────────────────────────────────────────────

def repartition_statut(date_debut: date, date_fin: date) -> list[dict]:
    """Distribution des escales par statut + pourcentages."""
    qs = Escale.objects.filter(date_arrivee__date__range=(date_debut, date_fin))
    total = qs.count()
    if total == 0:
        return []

    from apps.escales.models import Escale as EscaleModel
    statut_labels = dict(EscaleModel.Statut.choices)

    resultats = []
    for statut, count in qs.values_list("statut").annotate(n=Count("id_escale")).order_by("-n"):
        resultats.append({
            "statut": statut,
            "label": statut_labels.get(statut, statut),
            "nb_escales": count,
            "part_pct": _arrondir(count / total * 100),
        })
    return resultats


# ──────────────────────────────────────────────────────────────────────────────
# 6. Heatmap d'occupation des quais (semaine × poste)
# ──────────────────────────────────────────────────────────────────────────────

def heatmap_occupation(date_debut: date, date_fin: date) -> dict:
    """
    Calcule le taux d'occupation par semaine ISO et par poste.

    Retourne ::

        {
          "semaines": ["2026-W01", "2026-W02", ...],
          "postes": ["Poste A", "Poste B", ...],
          "matrice": [[12.5, 0.0, ...], ...]     # lignes = semaines
        }
    """
    qs = (
        Escale.objects.filter(
            date_depart__isnull=False,        # arrivee_poste
            date_appareillage__isnull=False,  # navire_appareille
            date_depart__date__range=(date_debut, date_fin),
        )
        .annotate(
            _semaine=ExtractWeek("date_depart"),
            _annee_sem=ExtractYear("date_depart"),
            _quai=F("poste__nom"),
        )
        .values("_semaine", "_annee_sem", "_quai", "date_depart", "date_appareillage")
    )

    # accumuler occupation par (annee, semaine, poste)
    occ: dict[tuple, float] = {}
    for row in qs:
        key = (row["_annee_sem"], row["_semaine"], row["_quai"])
        duree = max(
            (row["date_appareillage"] - row["date_depart"]).total_seconds() / 3600, 0
        )
        occ[key] = occ.get(key, 0) + duree

    # construire les axes
    semaines = sorted({(a, s) for a, s, _ in occ})
    postes = sorted({q for _, _, q in occ})

    heures_par_semaine = 7 * 24

    matrice = []
    for annee, sem in semaines:
        ligne = []
        for poste in postes:
            total_h = occ.get((annee, sem, poste), 0)
            taux = _arrondir(min(total_h / heures_par_semaine * 100, 100))
            ligne.append(taux)
        matrice.append(ligne)

    labels_semaines = [f"{a}-W{s:02d}" for a, s in semaines]

    return {
        "semaines": labels_semaines,
        "postes": postes,
        "matrice": matrice,
        "nb_semaines": len(semaines),
        "nb_postes": len(postes),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 7. Synthèse globale (tableau de bord analytique)
# ──────────────────────────────────────────────────────────────────────────────

def synthese_periode(date_debut: date, date_fin: date) -> dict:
    """
    Produit une synthèse analytique complète d'une période :
    KPI globaux + top terminaux + top compagnies + répartition statuts.
    """
    from .cube import MoteurCube, _agréger

    qs = Escale.objects.filter(date_arrivee__date__range=(date_debut, date_fin))

    agg = qs.aggregate(
        nb_escales=Count("id_escale"),
        temps_attente_moy=Avg("temps_attente"),
        temps_sejour_moy=Avg("temps_sejour"),
        tonnage_total_debarque=Sum("tonnage_debarque"),
        tonnage_total_embarque=Sum("tonnage_embarque"),
    )

    tonnage_total = (agg["tonnage_total_debarque"] or 0) + (agg["tonnage_total_embarque"] or 0)

    return {
        "periode": {
            "debut": date_debut.isoformat(),
            "fin": date_fin.isoformat(),
            "nb_jours": (date_fin - date_debut).days + 1,
        },
        "kpi_globaux": {
            "nb_escales": agg["nb_escales"] or 0,
            "temps_attente_moyen_h": _arrondir(agg["temps_attente_moy"]),
            "temps_sejour_moyen_h": _arrondir(agg["temps_sejour_moy"]),
            "tonnage_total_t": _arrondir(float(tonnage_total)) if tonnage_total else None,
        },
        "top_terminaux": classement("nb_escales", "terminal", date_debut, date_fin, top=5),
        "top_compagnies": classement("nb_escales", "compagnie", date_debut, date_fin, top=5),
        "repartition_statuts": repartition_statut(date_debut, date_fin),
    }

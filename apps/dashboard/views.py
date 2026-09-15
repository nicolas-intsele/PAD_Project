"""
Vues du module Tableau de bord (Module 5) et authentification.

Ce fichier contient :
  - Authentification (login / logout)
  - Vues Direction, Exploitation, Capitainerie, KPI, Analyse
  - Helpers partagés (_parse_dates, _safe_float, _tendance_json, _annees_disponibles)

Modules extraits lors de la refactorisation :
  - views_alerts.py    → Module 6 Alertes
  - views_reporting.py → Module 7 Reporting
  - views_users.py     → Module 8 Administration
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.analytics.analyses import (
    analyser_correlation,
    calculer_tendance,
    classement,
    comparer_periodes,
    heatmap_occupation,
    repartition_statut,
    synthese_periode,
)
from apps.analytics.cube import MoteurCube
from apps.analytics.models import AxeAnalyse, CubeAnalyse
from apps.escales.models import Escale
from apps.kpi.engine.view_helpers import (
    nb_escales_plage as nombre_escales,
    nb_arrivees_plage as nombre_arrivees,
    nb_departs_plage as nombre_departs,
    attente_plage as temps_attente_moyen,
    sejour_plage as temps_sejour_moyen,
    pilotage_plage as temps_pilotage_moyen,
    accostage_plage as temps_accostage_moyen,
    occupation_plage as taux_occupation_postes,
    rotation_plage as rotation_postes,
    productivite_plage as productivite,
    debit_plage as debit_postes,
)
from apps.kpi.engine.service import calculer_kpi_mois, garantir_catalogue
from apps.kpi.models import KPI, ValeurKPI
from apps.referentiel.models import Terminal, TypeNavire

logger = logging.getLogger(__name__)

def _parse_dates(request, default_days: int = 180):
    today = date.today()
    debut_def = (today - timedelta(days=default_days)).isoformat()
    fin_def = today.isoformat()
    try:
        d_debut = date.fromisoformat(request.GET.get("date_debut", debut_def))
        d_fin   = date.fromisoformat(request.GET.get("date_fin",   fin_def))
    except ValueError:
        d_debut = date.fromisoformat(debut_def)
        d_fin   = date.fromisoformat(fin_def)
    if d_debut > d_fin:
        d_debut, d_fin = d_fin, d_debut
    return d_debut, d_fin


def _safe_float(val, default=0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _tendance_json(mesure, d_debut, d_fin, granularite="mois"):
    try:
        r = calculer_tendance(mesure, d_debut, d_fin, granularite)
        labels = [p["label"] for p in r["serie"]]
        values = [_safe_float(p["valeur"]) for p in r["serie"]]
        reg = r.get("regression") or {}
        return {
            "labels": labels,
            "values": values,
            "valeurs_ajustees": reg.get("valeurs_ajustees", []),
            "tendance": reg.get("tendance", "stable"),
            "r_carre": reg.get("r_carre"),
        }
    except Exception:
        return {"labels": [], "values": [], "valeurs_ajustees": [], "tendance": "stable"}


def _annees_disponibles():
    from django.db.models.functions import ExtractYear
    years = (
        Escale.objects.annotate(yr=ExtractYear("date_arrivee"))
        .values_list("yr", flat=True)
        .distinct()
        .order_by("yr")
    )
    return sorted(set(y for y in years if y))


# ── Authentification ──────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:direction")
    error = False
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        if user:
            login(request, user)
            return redirect(request.POST.get("next") or "dashboard:direction")
        error = True
    from django.forms.utils import ErrorList
    class FakeForm:
        errors = error
    return render(request, "dashboard/login.html", {
        "form": FakeForm(),
        "next": request.GET.get("next", ""),
        "year": date.today().year,
    })


def logout_view(request):
    logout(request)
    return redirect("dashboard:login")


# ── Vue Direction ─────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def vue_direction(request):
    d_debut, d_fin = _parse_dates(request, 180)
    annees = _annees_disponibles()
    annee_n1 = int(request.GET.get("annee_n1", annees[0] if annees else date.today().year - 1))

    # KPI de la période courante
    nb_esc    = _safe_float(nombre_escales(d_debut, d_fin))
    t_attente = _safe_float(temps_attente_moyen(d_debut, d_fin))
    t_sejour  = _safe_float(temps_sejour_moyen(d_debut, d_fin))
    taux_occ  = _safe_float(taux_occupation_postes(d_debut, d_fin))
    ponct     = None  # KPI ponctualité supprimé
    rot       = _safe_float(rotation_postes(d_debut, d_fin))

    # Tonnage total (somme)
    from django.db.models import Sum
    qs = Escale.objects.filter(date_arrivee__date__range=(d_debut, d_fin))
    agg = qs.aggregate(d=Sum("tonnage_debarque"), e=Sum("tonnage_embarque"))
    tonnage = _safe_float((agg["d"] or 0) + (agg["e"] or 0))

    # Comparaison N-1 (même durée, décalée d'un an)
    duree = (d_fin - d_debut).days
    d_debut_n1 = d_debut.replace(year=d_debut.year - 1)
    d_fin_n1   = d_fin.replace(year=d_fin.year - 1)
    nb_esc_n1  = _safe_float(nombre_escales(d_debut_n1, d_fin_n1))
    delta_esc  = nb_esc - nb_esc_n1

    # Tendances pour Chart.js (plusieurs mesures)
    mesures_tendance = [
        "nb_escales", "temps_attente_moy",
        "taux_occupation",
    ]
    tendance_json = {}
    for m in mesures_tendance:
        tendance_json[m] = _tendance_json(m, d_debut, d_fin)

    # Donut terminaux
    term_data = classement("nb_escales", "terminal", d_debut, d_fin, top=20)
    terminaux_json = {
        "labels": [r["label"] for r in term_data],
        "values": [_safe_float(r["valeur"]) for r in term_data],
        "total":  sum(_safe_float(r["valeur"]) for r in term_data),
    }

    # Comparaison barres groupées (par terminal, période vs N-1)
    comp = comparer_periodes("nb_escales", "terminal", d_debut_n1, d_fin_n1, d_debut, d_fin)
    comparaison_json = {
        "labels": [r["label"] for r in comp],
        "ref":    [_safe_float(r["valeur_ref"])  for r in comp],
        "comp":   [_safe_float(r["valeur_comp"]) for r in comp],
    }

    # G3 : Tonnage mensuel débarqué vs embarqué
    from apps.kpi.engine.view_helpers import _mois_dans_plage
    from django.db.models import Sum as _Sum
    tonnage_mois_labels, tonn_deb_vals, tonn_emb_vals = [], [], []
    for annee, mois in _mois_dans_plage(d_debut, d_fin):
        cle = f"{annee}-{mois:02d}"
        agg2 = Escale.objects.filter(mois_source=cle).aggregate(
            d=_Sum("tonnage_debarque"), e=_Sum("tonnage_embarque")
        )
        tonnage_mois_labels.append(cle)
        tonn_deb_vals.append(_safe_float(agg2["d"] or 0))
        tonn_emb_vals.append(_safe_float(agg2["e"] or 0))
    tonnage_mensuel_json = {
        "labels": tonnage_mois_labels,
        "debarque": tonn_deb_vals,
        "embarque": tonn_emb_vals,
    }

    ctx = {
        "date_debut": d_debut.isoformat(),
        "date_fin":   d_fin.isoformat(),
        "annees_dispo": annees,
        "annee_n1": annee_n1,
        "kpi": {
            "nb_escales":         int(nb_esc),
            "nb_escales_trend":   "up" if delta_esc >= 0 else "down",
            "nb_escales_delta":   f"{delta_esc:+.0f} vs N-1",
            "temps_attente":      t_attente,
            "temps_attente_trend": "down" if t_attente < _safe_float(temps_attente_moyen(d_debut_n1, d_fin_n1)) else "up",
            "temps_attente_delta": "",
            "taux_occupation":    taux_occ,
            "tonnage_total":      tonnage,
            "temps_sejour":       t_sejour,
            "temps_pilotage":     _safe_float(temps_pilotage_moyen(d_debut, d_fin)),
            "rotation_postes":    rot,
            "debit_postes":       _safe_float(debit_postes(d_debut, d_fin)),
            "productivite":       _safe_float(productivite(d_debut, d_fin)),
        },
        "tendance_json":       tendance_json,
        "terminaux_json":      terminaux_json,
        "comparaison_json":    comparaison_json,
        "tonnage_mensuel_json": tonnage_mensuel_json,
    }
    return render(request, "dashboard/direction.html", ctx)


# ── Vue Exploitation ──────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def vue_exploitation(request):
    d_debut, d_fin = _parse_dates(request, 180)
    terminal_sel = request.GET.get("terminal", "")
    terminaux = list(Terminal.objects.values_list("nom", flat=True).order_by("nom"))

    # KPI globaux
    taux_occ  = _safe_float(taux_occupation_postes(d_debut, d_fin))
    rot       = _safe_float(rotation_postes(d_debut, d_fin))

    # Tonnage total de la période
    from django.db.models import Sum
    from apps.escales.models import Escale as EscaleModel
    qs_tonnage = EscaleModel.objects.filter(
        mois_source__isnull=False,
        date_arrivee__date__range=(d_debut, d_fin),
    )
    agg = qs_tonnage.aggregate(d=Sum("tonnage_debarque"), e=Sum("tonnage_embarque"))
    tonnage_debarque = _safe_float(agg["d"] or 0)
    tonnage_embarque = _safe_float(agg["e"] or 0)
    tonnage_total    = tonnage_debarque + tonnage_embarque

    # Occupation et attente par terminal
    occ_term  = classement("taux_occupation", "terminal", d_debut, d_fin, top=20, ordre="desc")
    att_term  = classement("temps_attente_moy", "terminal", d_debut, d_fin, top=20, ordre="desc")
    class_ter = classement("nb_escales", "terminal", d_debut, d_fin, top=10)

    # Occupation mensuelle
    occ_mens = _tendance_json("taux_occupation", d_debut, d_fin)

    # Heatmap
    try:
        hm = heatmap_occupation(d_debut, d_fin)
    except Exception:
        hm = {"semaines": [], "postes": [], "matrice": []}

    # G5 : nb escales par poste
    from django.db.models import Count as _Count, Avg as _Avg, Sum as _Sum
    from apps.kpi.engine.view_helpers import _mois_dans_plage
    import calendar as _cal
    postes_data = list(
        Escale.objects.filter(date_arrivee__date__range=(d_debut, d_fin))
        .values("poste__nom")
        .annotate(n=_Count("id_escale"), sejour=_Avg("temps_sejour"),
                  tonn=_Sum("tonnage_debarque"))
        .order_by("-n")[:20]
    )
    postes_escales_json = {
        "labels": [p["poste__nom"] for p in postes_data],
        "escales": [p["n"] for p in postes_data],
        "sejour":  [round(float(p["sejour"] or 0), 1) for p in postes_data],
    }

    # G9 : tonnage par terminal
    tonn_term = list(
        Escale.objects.filter(date_arrivee__date__range=(d_debut, d_fin))
        .values("poste__terminal__nom")
        .annotate(deb=_Sum("tonnage_debarque"), emb=_Sum("tonnage_embarque"))
        .order_by("-deb")
    )
    tonnage_terminal_json = {
        "labels": [t["poste__terminal__nom"] for t in tonn_term],
        "debarque": [_safe_float(t["deb"] or 0) for t in tonn_term],
        "embarque": [_safe_float(t["emb"] or 0) for t in tonn_term],
    }

    ctx = {
        "date_debut": d_debut.isoformat(),
        "date_fin":   d_fin.isoformat(),
        "terminaux":  terminaux,
        "terminal_sel": terminal_sel,
        "kpi": {
            "taux_occupation":  taux_occ,
            "rotation_postes":  rot,
            "debit_postes":     _safe_float(debit_postes(d_debut, d_fin)),
            "temps_sejour":     _safe_float(temps_sejour_moyen(d_debut, d_fin)),
            "tonnage_debarque": tonnage_debarque,
            "tonnage_embarque": tonnage_embarque,
            "tonnage_total":    tonnage_total,
        },
        "classement_terminaux": class_ter,
        "occupation_terminaux_json": {
            "labels": [r["label"] for r in occ_term],
            "values": [_safe_float(r["valeur"]) for r in occ_term],
        },
        "attente_terminaux_json": {
            "labels": [r["label"] for r in att_term],
            "values": [_safe_float(r["valeur"]) for r in att_term],
        },
        "heatmap_json":          hm,
        "occ_mensuel_json":       occ_mens,
        "postes_escales_json":    postes_escales_json,
        "tonnage_terminal_json":  tonnage_terminal_json,
    }
    return render(request, "dashboard/exploitation.html", ctx)


# ── Vue DAPC ──────────────────────────────────────────────────────────────────

def _require_dapc(request):
    """Retourne True si l'utilisateur a accès à la vue DAPC."""
    if request.user.is_staff or request.user.is_superuser:
        return True
    try:
        role = request.user.profil.role
        return role and role.code in ("dapc", "admin")
    except Exception:
        return False


@login_required(login_url="dashboard:login")
def vue_dapc(request):
    if not _require_dapc(request):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Accès réservé au service DAPC.")

    d_debut, d_fin = _parse_dates(request, 180)
    terminal_sel = request.GET.get("terminal", "")
    terminaux = list(Terminal.objects.values_list("nom", flat=True).order_by("nom"))
    annees = _annees_disponibles()
    annee_n1 = int(request.GET.get("annee_n1", annees[0] if annees else date.today().year - 1))

    # ── KPI direction ─────────────────────────────────────────────────────────
    nb_esc    = _safe_float(nombre_escales(d_debut, d_fin))
    t_attente = _safe_float(temps_attente_moyen(d_debut, d_fin))
    t_sejour  = _safe_float(temps_sejour_moyen(d_debut, d_fin))
    taux_occ  = _safe_float(taux_occupation_postes(d_debut, d_fin))
    rot       = _safe_float(rotation_postes(d_debut, d_fin))

    d_debut_n1 = d_debut.replace(year=d_debut.year - 1)
    d_fin_n1   = d_fin.replace(year=d_fin.year - 1)
    nb_esc_n1  = _safe_float(nombre_escales(d_debut_n1, d_fin_n1))
    delta_esc  = nb_esc - nb_esc_n1

    # ── Tonnage ───────────────────────────────────────────────────────────────
    from django.db.models import Sum as _Sum
    qs_t = Escale.objects.filter(
        mois_source__isnull=False,
        date_arrivee__date__range=(d_debut, d_fin),
    )
    agg = qs_t.aggregate(d=_Sum("tonnage_debarque"), e=_Sum("tonnage_embarque"))
    tonnage_debarque = _safe_float(agg["d"] or 0)
    tonnage_embarque = _safe_float(agg["e"] or 0)
    tonnage_total    = tonnage_debarque + tonnage_embarque

    # ── Graphiques direction ──────────────────────────────────────────────────
    mesures_tendance = ["nb_escales", "temps_attente_moy", "taux_occupation"]
    tendance_json = {}
    for m in mesures_tendance:
        tendance_json[m] = _tendance_json(m, d_debut, d_fin)

    term_data = classement("nb_escales", "terminal", d_debut, d_fin, top=20)
    terminaux_json = {
        "labels": [r["label"] for r in term_data],
        "values": [_safe_float(r["valeur"]) for r in term_data],
        "total":  sum(_safe_float(r["valeur"]) for r in term_data),
    }

    comp = comparer_periodes("nb_escales", "terminal", d_debut_n1, d_fin_n1, d_debut, d_fin)
    comparaison_json = {
        "labels": [r["label"] for r in comp],
        "ref":    [_safe_float(r["valeur_ref"])  for r in comp],
        "comp":   [_safe_float(r["valeur_comp"]) for r in comp],
    }

    from apps.kpi.engine.view_helpers import _mois_dans_plage
    tonn_labels, tonn_deb_vals, tonn_emb_vals = [], [], []
    for annee, mois in _mois_dans_plage(d_debut, d_fin):
        cle = f"{annee}-{mois:02d}"
        agg2 = Escale.objects.filter(mois_source=cle).aggregate(
            d=_Sum("tonnage_debarque"), e=_Sum("tonnage_embarque")
        )
        tonn_labels.append(cle)
        tonn_deb_vals.append(_safe_float(agg2["d"] or 0))
        tonn_emb_vals.append(_safe_float(agg2["e"] or 0))
    tonnage_mensuel_json = {
        "labels":   tonn_labels,
        "debarque": tonn_deb_vals,
        "embarque": tonn_emb_vals,
    }

    # ── Graphiques exploitation ───────────────────────────────────────────────
    from django.db.models import Count as _Count, Avg as _Avg

    occ_term  = classement("taux_occupation",   "terminal", d_debut, d_fin, top=20, ordre="desc")
    att_term  = classement("temps_attente_moy", "terminal", d_debut, d_fin, top=20, ordre="desc")
    class_ter = classement("nb_escales",        "terminal", d_debut, d_fin, top=10)
    occ_mens  = _tendance_json("taux_occupation", d_debut, d_fin)

    try:
        hm = heatmap_occupation(d_debut, d_fin)
    except Exception:
        hm = {"semaines": [], "postes": [], "matrice": []}

    postes_data = list(
        Escale.objects.filter(date_arrivee__date__range=(d_debut, d_fin))
        .values("poste__nom")
        .annotate(n=_Count("id_escale"), sejour=_Avg("temps_sejour"))
        .order_by("-n")[:20]
    )
    postes_escales_json = {
        "labels": [p["poste__nom"] for p in postes_data],
        "escales": [p["n"] for p in postes_data],
        "sejour":  [round(float(p["sejour"] or 0), 1) for p in postes_data],
    }

    tonn_term = list(
        Escale.objects.filter(date_arrivee__date__range=(d_debut, d_fin))
        .values("poste__terminal__nom")
        .annotate(deb=_Sum("tonnage_debarque"), emb=_Sum("tonnage_embarque"))
        .order_by("-deb")
    )
    tonnage_terminal_json = {
        "labels":   [t["poste__terminal__nom"] for t in tonn_term],
        "debarque": [_safe_float(t["deb"] or 0) for t in tonn_term],
        "embarque": [_safe_float(t["emb"] or 0) for t in tonn_term],
    }

    ctx = {
        "date_debut":  d_debut.isoformat(),
        "date_fin":    d_fin.isoformat(),
        "annees_dispo": annees,
        "annee_n1":    annee_n1,
        "terminaux":   terminaux,
        "terminal_sel": terminal_sel,
        "kpi": {
            "nb_escales":        int(nb_esc),
            "nb_escales_trend":  "up" if delta_esc >= 0 else "down",
            "nb_escales_delta":  f"{delta_esc:+.0f} vs N-1",
            "temps_attente":     t_attente,
            "temps_attente_trend": "down" if t_attente < _safe_float(temps_attente_moyen(d_debut_n1, d_fin_n1)) else "up",
            "taux_occupation":   taux_occ,
            "temps_sejour":      t_sejour,
            "temps_pilotage":    _safe_float(temps_pilotage_moyen(d_debut, d_fin)),
            "rotation_postes":   rot,
            "debit_postes":      _safe_float(debit_postes(d_debut, d_fin)),
            "productivite":      _safe_float(productivite(d_debut, d_fin)),
            "tonnage_debarque":  tonnage_debarque,
            "tonnage_embarque":  tonnage_embarque,
            "tonnage_total":     tonnage_total,
        },
        "classement_terminaux":    class_ter,
        "tendance_json":           tendance_json,
        "terminaux_json":          terminaux_json,
        "comparaison_json":        comparaison_json,
        "tonnage_mensuel_json":    tonnage_mensuel_json,
        "occupation_terminaux_json": {
            "labels": [r["label"] for r in occ_term],
            "values": [_safe_float(r["valeur"]) for r in occ_term],
        },
        "attente_terminaux_json": {
            "labels": [r["label"] for r in att_term],
            "values": [_safe_float(r["valeur"]) for r in att_term],
        },
        "heatmap_json":           hm,
        "occ_mensuel_json":       occ_mens,
        "postes_escales_json":    postes_escales_json,
        "tonnage_terminal_json":  tonnage_terminal_json,
    }
    return render(request, "dashboard/dapc.html", ctx)

@login_required(login_url="dashboard:login")
def vue_capitainerie(request):
    d_debut, d_fin = _parse_dates(request, 180)
    type_sel = request.GET.get("type_navire", "")
    types_navires = list(TypeNavire.objects.values_list("libelle", flat=True).order_by("libelle"))

    # Filtrage optionnel par type de navire
    qs_base = Escale.objects.filter(date_arrivee__date__range=(d_debut, d_fin))
    if type_sel:
        qs_base = qs_base.filter(navire__type_navire__libelle=type_sel)

    # Statuts
    statuts = repartition_statut(d_debut, d_fin)
    nb_terminees = next((s["nb_escales"] for s in statuts if s["statut"] == "terminee"), 0)

    # Scinder les escales "en cours" : navires à poste vs navires en rade
    en_cours_qs = Escale.objects.filter(
        date_arrivee__date__range=(d_debut, d_fin),
        statut=Escale.Statut.EN_COURS,
    )
    nb_a_poste = en_cours_qs.filter(date_depart__isnull=False).count()
    nb_en_rade = en_cours_qs.filter(date_depart__isnull=True).count()
    nb_en_cours = nb_a_poste + nb_en_rade

    # KPI
    pilotage  = _safe_float(temps_pilotage_moyen(d_debut, d_fin))
    accostage = _safe_float(temps_accostage_moyen(d_debut, d_fin))

    # Ponctualité mensuelle
    ponct_json = {"labels": [], "values": []}  # KPI ponctualité supprimé

    # Classement compagnies
    class_comp = classement("nb_escales", "compagnie", d_debut, d_fin, top=10)

    # G10 : Répartition par type de navire
    from django.db.models import Count as _Count, Avg as _Avg
    types_raw = list(
        qs_base.values("navire__type_navire__libelle")
        .annotate(n=_Count("id_escale"), att=_Avg("temps_attente"), sej=_Avg("temps_sejour"))
        .order_by("-n")
    )
    # Regrouper les petits types (<3 escales) en "Autres"
    SEUIL_AUTRE = 3
    types_principaux = [t for t in types_raw if t["n"] >= SEUIL_AUTRE]
    nb_autres = sum(t["n"] for t in types_raw if t["n"] < SEUIL_AUTRE)
    if nb_autres:
        types_principaux.append({"navire__type_navire__libelle": "Autres", "n": nb_autres, "att": None, "sej": None})

    types_navires_json = {
        "labels":  [t["navire__type_navire__libelle"] for t in types_principaux],
        "escales": [t["n"] for t in types_principaux],
        "attente": [round(float(t["att"] or 0), 1) for t in types_principaux],
        "sejour":  [round(float(t["sej"] or 0), 1) for t in types_principaux],
    }

    # G12 : Top compagnies
    compagnies_raw = list(
        qs_base.values("navire__compagnie__raison_sociale")
        .annotate(n=_Count("id_escale"))
        .order_by("-n")[:10]
    )
    compagnies_json = {
        "labels":  [r["navire__compagnie__raison_sociale"] or "Inconnu" for r in compagnies_raw],
        "escales": [r["n"] for r in compagnies_raw],
    }

    # G13 : Évolution mensuelle attente vs séjour
    from apps.kpi.engine.view_helpers import _mois_dans_plage
    mois_labels, att_vals, sej_vals = [], [], []
    for annee, mois in _mois_dans_plage(d_debut, d_fin):
        cle = f"{annee}-{mois:02d}"
        agg = Escale.objects.filter(mois_source=cle).aggregate(
            att=_Avg("temps_attente"), sej=_Avg("temps_sejour")
        )
        mois_labels.append(cle)
        att_vals.append(round(float(agg["att"] or 0), 1))
        sej_vals.append(round(float(agg["sej"] or 0), 1))
    evolution_temps_json = {
        "labels":  mois_labels,
        "attente": att_vals,
        "sejour":  sej_vals,
    }

    # G14 : Distribution des durées de séjour (histogramme en tranches de 24h)
    from collections import Counter
    sejours = list(qs_base.filter(temps_sejour__isnull=False, temps_sejour__gte=0)
                   .values_list("temps_sejour", flat=True))
    tranches = ["0-24h","24-48h","48-72h","72-96h","96-120h","120-168h",">168h"]
    limites  = [0, 24, 48, 72, 96, 120, 168, float("inf")]
    distrib  = [0] * len(tranches)
    for s in sejours:
        for i in range(len(limites)-1):
            if limites[i] <= float(s) < limites[i+1]:
                distrib[i] += 1
                break
    distribution_sejour_json = {"labels": tranches, "values": distrib}

    # Stats par type de navire (conservé pour compatibilité)
    from apps.analytics.cube import MoteurCube
    types_data_raw = MoteurCube("nb_escales", "type_navire", date_debut=d_debut, date_fin=d_fin).calculer_plat()
    att_raw        = MoteurCube("temps_attente_moy", "type_navire", date_debut=d_debut, date_fin=d_fin).calculer_plat()
    pilot_raw      = MoteurCube("temps_pilotage_moy", "type_navire", date_debut=d_debut, date_fin=d_fin).calculer_plat()
    types_labels   = [r["label"] for r in types_data_raw]
    types_escales  = [_safe_float(r["valeur"]) for r in types_data_raw]
    att_map        = {r["groupe"]: _safe_float(r["valeur"]) for r in att_raw}
    pilot_map      = {r["groupe"]: _safe_float(r["valeur"]) for r in pilot_raw}
    types_attente  = [att_map.get(r["groupe"], 0) for r in types_data_raw]
    types_pilotage = [pilot_map.get(r["groupe"], 0) for r in types_data_raw]

    # Escales récentes
    escales_recentes = (
        qs_base
        .select_related("navire__type_navire", "navire__compagnie", "poste__terminal")
        .order_by("-date_arrivee")[:20]
    )

    ctx = {
        "date_debut": d_debut.isoformat(),
        "date_fin":   d_fin.isoformat(),
        "types_navires": types_navires,
        "type_sel": type_sel,
        "stats": {
            "nb_terminees": nb_terminees,
            "nb_en_cours":  nb_en_cours,
            "nb_a_poste":   nb_a_poste,
            "nb_en_rade":   nb_en_rade,
        },
        "kpi": {"temps_pilotage": pilotage, "temps_accostage": accostage},
        "classement_compagnies": class_comp,
        "escales_recentes": escales_recentes,
        "types_navires_json":       types_navires_json,
        "compagnies_json":          compagnies_json,
        "evolution_temps_json":     evolution_temps_json,
        "distribution_sejour_json": distribution_sejour_json,
        "statuts_json": {
            "labels": ["Terminée", "À poste", "En rade"],
            "values": [nb_terminees, nb_a_poste, nb_en_rade],
            "codes":  ["terminee", "a_poste", "en_rade"],
        },
        "types_navires_json": {
            "labels":   types_labels,
            "escales":  types_escales,
            "attente":  types_attente,
            "pilotage": types_pilotage,
        },
        "ponct_supprime": True,  # KPI ponctualité supprimé
    }
    return render(request, "dashboard/capitainerie.html", ctx)


# ── Page KPI avec filtres ─────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def vue_kpi(request):
    d_debut, d_fin = _parse_dates(request, 365)
    categorie   = request.GET.get("categorie", "")
    terminal_sel = request.GET.get("terminal", "")
    granularite = request.GET.get("granularite", "mois")

    terminaux = list(Terminal.objects.values_list("nom", flat=True).order_by("nom"))
    garantir_catalogue()
    kpis_qs = KPI.objects.all()
    if categorie:
        kpis_qs = kpis_qs.filter(categorie=categorie)
    kpis_list = list(kpis_qs)

    # Lignes du tableau : valeurs issues de ValeurKPI en base (calculées par mois)
    # On prend la valeur du dernier mois disponible dans la plage
    from apps.kpi.engine.view_helpers import _mois_dans_plage
    mois_plage = _mois_dans_plage(d_debut, d_fin)
    kpi_rows = []
    for kpi in kpis_list:
        # Chercher la dernière ValeurKPI dans la période
        derniere_valeur = (
            ValeurKPI.objects
            .filter(kpi=kpi, date_ref__date_calendaire__range=(d_debut, d_fin))
            .order_by("-date_ref__date_calendaire")
            .first()
        )
        valeur = derniere_valeur.valeur if derniere_valeur else None

        # Tendance sur la période
        tendance = "stable"
        try:
            from apps.kpi.models import ValeurKPI as VK
            vals = list(
                VK.objects.filter(kpi=kpi, date_ref__date_calendaire__range=(d_debut, d_fin))
                .order_by("date_ref__date_calendaire")
                .values_list("valeur", flat=True)
            )
            if len(vals) >= 2:
                delta = float(vals[-1]) - float(vals[0])
                if abs(delta) < 0.01:
                    tendance = "stable"
                elif delta > 0:
                    tendance = "hausse"
                else:
                    tendance = "baisse"
        except Exception:
            pass

        kpi_rows.append({
            "code": kpi.code,
            "libelle": kpi.libelle,
            "categorie": kpi.categorie,
            "unite": kpi.unite or "",
            "valeur": valeur,
            "periode": f"{d_debut} → {d_fin}",
            "tendance": tendance,
        })

    # Résumé par catégorie
    resume_categories = {}
    for kpi in kpis_list:
        cat = kpi.categorie
        resume_categories.setdefault(cat, {"nb_kpi": 0})
        resume_categories[cat]["nb_kpi"] += 1

    # Tendances pour Chart.js (tous les KPI)
    mesure_map = {
        "TRAFIC_NB_ESCALES": "nb_escales", "TRAFIC_NB_ARRIVEES": "nb_arrivees",
        "TRAFIC_NB_DEPARTS": "nb_departs", "TEMPS_ATTENTE_MOYEN": "temps_attente_moy",
        "TEMPS_SEJOUR_MOYEN": "temps_sejour_moy", "TEMPS_PILOTAGE_MOYEN": "temps_pilotage_moy",
        "TEMPS_ACCOSTAGE_MOYEN": "temps_attente_moy",
        "INFRA_TAUX_OCCUPATION": "taux_occupation", "INFRA_ROTATION_QUAIS": "nb_escales",
        "INFRA_DISPONIBILITE_POSTES": "taux_occupation", "PERF_PRODUCTIVITE": "tonnage_total",
            }
    all_tendances = {}
    for kpi in KPI.objects.all():
        m = mesure_map.get(kpi.code, "nb_escales")
        all_tendances[kpi.code] = _tendance_json(m, d_debut, d_fin, granularite)

    # Radar (performance normalisée 0-100 par catégorie)
    radar_cats = {"trafic": 0.0, "temps": 0.0, "infrastructures": 0.0, "performance": 0.0}
    counts = {k: 0 for k in radar_cats}
    for row in kpi_rows:
        cat = row["categorie"]
        if cat not in radar_cats or row["valeur"] is None:
            continue
        v = _safe_float(row["valeur"])
        code = row["code"]
        # Normalisation par indicateur
        if code in ("TRAFIC_NB_ESCALES", "TRAFIC_NB_ARRIVEES", "TRAFIC_NB_DEPARTS"):
            radar_cats[cat] += min(v / 150 * 100, 100)
        elif code in ("TEMPS_ATTENTE_MOYEN", "TEMPS_SEJOUR_MOYEN"):
            # Moins c'est long, mieux c'est → inverser
            radar_cats[cat] += max(0, 100 - v / 200 * 100)
        elif code in ("TEMPS_PILOTAGE_MOYEN", "TEMPS_ACCOSTAGE_MOYEN"):
            radar_cats[cat] += max(0, 100 - v / 5 * 100)
        elif code == "INFRA_TAUX_OCCUPATION":
            radar_cats[cat] += min(v, 100)
        elif code == "INFRA_ROTATION_POSTES":
            radar_cats[cat] += min(v / 15 * 100, 100)
        elif code == "PERF_PRODUCTIVITE":
            radar_cats[cat] += min(v / 500 * 100, 100)
        elif code == "PERF_DEBIT_POSTES":
            radar_cats[cat] += min(v / 1 * 100, 100)
        counts[cat] += 1

    radar_values = [
        round(radar_cats[k] / counts[k], 1) if counts.get(k, 0) > 0 else 0
        for k in radar_cats
    ]
    labels_fr = {
        "trafic": "Trafic", "temps": "Temps",
        "infrastructures": "Infrastructure", "performance": "Performance"
    }

    ctx = {
        "date_debut": d_debut.isoformat(),
        "date_fin":   d_fin.isoformat(),
        "categorie":  categorie,
        "terminal_sel": terminal_sel,
        "granularite": granularite,
        "terminaux":  terminaux,
        "kpis_list":  kpis_list,
        "kpi_rows":   kpi_rows,
        "resume_categories": resume_categories,
        "all_tendances_json": all_tendances,
        "radar_json": {
            "labels": [labels_fr[k] for k in radar_cats],
            "values": radar_values,
        },
    }
    return render(request, "dashboard/kpi.html", ctx)


# ── Analyse OLAP ──────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def vue_analyse(request):
    d_debut, d_fin = _parse_dates(request, 365)
    mesure_sel     = request.GET.get("mesure", "nb_escales")
    axe_ligne_sel  = request.GET.get("axe_ligne", "terminal")
    axe_colonne_sel = request.GET.get("axe_colonne", "")

    axes   = [{"code": c, "libelle": l} for c, l in AxeAnalyse.Type.choices]
    mesures = [{"code": c, "libelle": l} for c, l in CubeAnalyse.Mesure.choices]

    resultats = []
    resume = None
    try:
        moteur = MoteurCube(
            mesure=mesure_sel,
            axe_ligne=axe_ligne_sel,
            axe_colonne=axe_colonne_sel or None,
            date_debut=d_debut,
            date_fin=d_fin,
        )
        resultats = moteur.calculer_plat()
        resume    = moteur.calculer_resume()
    except Exception as exc:
        logger.warning("Erreur calcul cube: %s", exc)

    ctx = {
        "date_debut": d_debut.isoformat(),
        "date_fin":   d_fin.isoformat(),
        "axes":    axes,
        "mesures": mesures,
        "mesure_sel":      mesure_sel,
        "axe_ligne_sel":   axe_ligne_sel,
        "axe_colonne_sel": axe_colonne_sel,
        "resultats": resultats,
        "resume":    resume,
        "cube_json": resultats,
    }
    return render(request, "dashboard/analyse.html", ctx)


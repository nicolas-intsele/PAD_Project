"""
Vues du module Alertes (Module 6).
Extraites de apps/dashboard/views.py lors de la refactorisation (Phase 9).
"""
from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)


@login_required(login_url="dashboard:login")
def vue_alertes(request):
    from apps.alerts.models import Alerte
    from apps.alerts.service import stats_alertes
    from django.core.paginator import Paginator

    gravite     = request.GET.get("gravite", "")
    type_alerte = request.GET.get("type_alerte", "")
    statut      = request.GET.get("statut", "active")

    qs = Alerte.objects.all().order_by("-date_declenchement")
    if gravite:
        qs = qs.filter(niveau_gravite=gravite)
    if type_alerte:
        qs = qs.filter(type_alerte=type_alerte)
    if statut:
        qs = qs.filter(statut=statut)

    paginator = Paginator(qs, 20)
    alertes = paginator.get_page(request.GET.get("page", 1))

    return render(request, "alerts/centre.html", {
        "alertes": alertes,
        "gravite": gravite,
        "type_alerte": type_alerte,
        "statut": statut,
        "stats": stats_alertes(),
        "alertes_actives_count": Alerte.objects.filter(statut="active").count(),
    })


@login_required(login_url="dashboard:login")
def alerte_acquitter(request, pk):
    from apps.alerts.models import Alerte
    from django.contrib import messages as dj_messages
    if request.method == "POST":
        try:
            a = Alerte.objects.get(pk=pk)
            a.acquitter(request.user)
            dj_messages.success(request, f"Alerte #{pk} acquittée.")
        except Alerte.DoesNotExist:
            pass
    return redirect("dashboard:alertes")


@login_required(login_url="dashboard:login")
def alerte_resoudre(request, pk):
    from apps.alerts.models import Alerte
    from django.contrib import messages as dj_messages
    if request.method == "POST":
        try:
            a = Alerte.objects.get(pk=pk)
            a.resoudre()
            dj_messages.success(request, f"Alerte #{pk} marquée comme résolue.")
        except Alerte.DoesNotExist:
            pass
    return redirect("dashboard:alertes")


@login_required(login_url="dashboard:login")
def alertes_acquitter_tout(request):
    from apps.alerts.models import Alerte
    from django.contrib import messages as dj_messages
    if request.method == "POST":
        actives = Alerte.objects.filter(statut="active")
        n = actives.count()
        for a in actives:
            a.acquitter(request.user)
        dj_messages.success(request, f"{n} alerte(s) acquittée(s).")
    return redirect("dashboard:alertes")


@login_required(login_url="dashboard:login")
def alertes_scanner(request):
    """Lance un scan d'alertes et redirige vers le centre."""
    from apps.alerts.service import scanner_alertes
    from django.contrib import messages as dj_messages
    result = scanner_alertes()
    dj_messages.success(
        request,
        f"Scan terminé : {result['total']} nouvelle(s) alerte(s) créée(s) "
        f"(KPI : {result['alertes_kpi']}, escales : {result['alertes_escales']})"
    )
    return redirect("dashboard:alertes")

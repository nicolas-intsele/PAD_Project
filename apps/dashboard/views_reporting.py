"""
Vues du module Reporting (Module 7).
Extraites de apps/dashboard/views.py lors de la refactorisation (Phase 9).
"""
from __future__ import annotations

import logging
from datetime import date as _date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)


@login_required(login_url="dashboard:login")
def vue_reporting(request):
    from apps.reporting.models import Rapport

    today = _date.today()
    rapports = Rapport.objects.filter(utilisateur=request.user).order_by("-date_generation")[:20]

    message      = request.session.pop("rapport_message", None)
    message_type = request.session.pop("rapport_message_type", "success")

    return render(request, "reporting/reporting.html", {
        "rapports": rapports,
        "date_debut_defaut": today.replace(day=1).isoformat(),
        "date_fin_defaut":   today.isoformat(),
        "message":      message,
        "message_type": message_type,
    })


@login_required(login_url="dashboard:login")
def reporting_generer(request):
    """POST : génère le rapport, sauvegarde et renvoie en téléchargement."""
    if request.method != "POST":
        return redirect("dashboard:reporting")

    from django.http import HttpResponse
    from django.core.files.base import ContentFile
    from apps.reporting.models import Rapport
    from apps.reporting.generators.pdf_generator import generer_pdf
    from apps.reporting.generators.excel_generator import generer_excel

    type_rapport = request.POST.get("type_rapport", "mensuel")
    fmt          = request.POST.get("format", "pdf")
    try:
        d_debut = _date.fromisoformat(request.POST.get("date_debut", ""))
        d_fin   = _date.fromisoformat(request.POST.get("date_fin", ""))
    except ValueError:
        today   = _date.today()
        d_debut = today.replace(day=1)
        d_fin   = today

    try:
        if fmt == "pdf":
            content = generer_pdf(d_debut, d_fin, type_rapport)
            mime    = "application/pdf"
            ext     = "pdf"
        else:
            content = generer_excel(d_debut, d_fin, type_rapport)
            mime    = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ext     = "xlsx"

        filename = f"PAD_rapport_{type_rapport}_{d_debut}_{d_fin}.{ext}"

        rapport = Rapport.objects.create(
            utilisateur=request.user,
            type_rapport=type_rapport,
            periode_debut=d_debut,
            periode_fin=d_fin,
            format=fmt,
            titre=f"Rapport {type_rapport} — {d_debut} → {d_fin}",
            taille_octets=len(content),
        )
        rapport.fichier.save(filename, ContentFile(content), save=True)

        response = HttpResponse(content, content_type=mime)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    except Exception as exc:
        logger.exception("Erreur génération rapport")
        request.session["rapport_message"]      = f"Erreur lors de la génération : {exc}"
        request.session["rapport_message_type"] = "danger"
        return redirect("dashboard:reporting")


@login_required(login_url="dashboard:login")
def reporting_telecharger(request, pk):
    """Télécharge un rapport déjà généré."""
    from django.http import HttpResponse, Http404
    from apps.reporting.models import Rapport

    try:
        rapport = Rapport.objects.get(pk=pk, utilisateur=request.user)
    except Rapport.DoesNotExist:
        raise Http404

    if not rapport.fichier:
        raise Http404

    with rapport.fichier.open("rb") as f:
        content = f.read()

    mime = "application/pdf" if rapport.format == "pdf" else \
           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response = HttpResponse(content, content_type=mime)
    response["Content-Disposition"] = f'attachment; filename="{rapport.fichier.name.split("/")[-1]}"'
    return response


@login_required(login_url="dashboard:login")
def reporting_rapide(request, type: str, format: str):
    """Génère un rapport rapide (mois en cours ou semaine) sans formulaire."""
    today = _date.today()

    if type == "hebdomadaire":
        d_debut = today - timedelta(days=today.weekday())
        d_fin   = today
    elif type == "journalier":
        d_debut = d_fin = today
    else:  # mensuel
        d_debut = today.replace(day=1)
        d_fin   = today

    request.method      = "POST"
    request.POST        = request.POST.copy()
    request.POST["type_rapport"] = type
    request.POST["format"]       = format
    request.POST["date_debut"]   = d_debut.isoformat()
    request.POST["date_fin"]     = d_fin.isoformat()
    return reporting_generer(request)

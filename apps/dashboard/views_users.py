"""
Vues du module Administration & Utilisateurs (Module 8).
Extraites de apps/dashboard/views.py lors de la refactorisation (Phase 9).
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from functools import wraps

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)


# ── Décorateur admin ──────────────────────────────────────────────────────────

def _admin_only(view_fn):
    """Réserve la vue aux superusers ou rôle admin."""
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("dashboard:login")
        if not (request.user.is_superuser or request.user.is_staff):
            from django.contrib import messages as dj_messages
            dj_messages.error(request, "Accès réservé aux administrateurs.")
            return redirect("dashboard:direction")
        return view_fn(request, *args, **kwargs)
    return wrapper


# ── Vues administration ───────────────────────────────────────────────────────

@_admin_only
def vue_administration(request):
    from apps.users.models import ProfilUtilisateur, JournalAction, Role
    from apps.kpi.models import SeuilAlerte
    from apps.alerts.models import Alerte
    from apps.escales.models import Escale
    from django.contrib.auth.models import User
    import django

    today     = date.today()
    sept_jours = today - timedelta(days=7)

    nb_users           = User.objects.count()
    nb_actifs          = User.objects.filter(is_active=True).count()
    nb_seuils          = SeuilAlerte.objects.count()
    nb_alertes_actives = Alerte.objects.filter(statut="active").count()
    nb_actions_7j      = JournalAction.objects.filter(date_action__date__gte=sept_jours).count()

    roles_data = {"labels": [], "values": []}
    for r in Role.objects.all():
        count = ProfilUtilisateur.objects.filter(role=r).count()
        roles_data["labels"].append(r.libelle)
        roles_data["values"].append(count)
    sans_role = ProfilUtilisateur.objects.filter(role__isnull=True).count()
    if sans_role:
        roles_data["labels"].append("Sans rôle")
        roles_data["values"].append(sans_role)

    dernieres_actions = JournalAction.objects.select_related("utilisateur").order_by("-date_action")[:10]

    system_info = [
        {"label": "Version Django",     "valeur": django.__version__},
        {"label": "Total escales",      "valeur": Escale.objects.count()},
        {"label": "Total utilisateurs", "valeur": nb_users},
        {"label": "Alertes actives",    "valeur": nb_alertes_actives},
    ]

    return render(request, "users/administration.html", {
        "stats": {
            "nb_users": nb_users,
            "nb_actifs": nb_actifs,
            "nb_seuils": nb_seuils,
            "nb_alertes_actives": nb_alertes_actives,
            "nb_actions_7j": nb_actions_7j,
        },
        "roles_json":        json.dumps(roles_data),
        "dernières_actions": dernieres_actions,
        "system_info":       system_info,
    })


@_admin_only
def vue_admin_utilisateurs(request):
    from django.contrib.auth.models import User
    from django.db import models
    from apps.users.models import Role

    q        = request.GET.get("q", "")
    role_sel = request.GET.get("role", "")
    actif_sel = request.GET.get("actif", "1")

    qs = User.objects.select_related("profil__role").order_by("username")
    if q:
        qs = qs.filter(
            models.Q(username__icontains=q) |
            models.Q(first_name__icontains=q) |
            models.Q(last_name__icontains=q) |
            models.Q(email__icontains=q)
        )
    if role_sel:
        qs = qs.filter(profil__role__code=role_sel)
    if actif_sel == "1":
        qs = qs.filter(is_active=True)
    elif actif_sel == "0":
        qs = qs.filter(is_active=False)

    return render(request, "users/utilisateurs.html", {
        "utilisateurs": qs,
        "roles":        Role.objects.all(),
        "role_sel":     role_sel,
        "actif_sel":    actif_sel,
        "q":            q,
    })


@_admin_only
def vue_admin_user_form(request, pk=None):
    from django.contrib.auth.models import User
    from django.contrib import messages as dj_messages
    from apps.users.models import Role, ProfilUtilisateur, journaliser

    user_obj = None
    if pk:
        try:
            user_obj = User.objects.select_related("profil__role").get(pk=pk)
        except User.DoesNotExist:
            raise

    ctx = {"user_obj": user_obj, "roles": Role.objects.all()}

    if request.method == "POST":
        username   = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name  = request.POST.get("last_name", "").strip()
        email      = request.POST.get("email", "").strip()
        pwd1       = request.POST.get("password1", "")
        pwd2       = request.POST.get("password2", "")
        role_pk    = request.POST.get("role", "")
        poste      = request.POST.get("poste", "")
        telephone  = request.POST.get("telephone", "")
        actif      = bool(request.POST.get("actif"))

        if not username:
            dj_messages.error(request, "L'identifiant est obligatoire.")
        elif not user_obj and User.objects.filter(username=username).exists():
            dj_messages.error(request, f"L'identifiant « {username} » est déjà pris.")
        elif pwd1 and pwd1 != pwd2:
            dj_messages.error(request, "Les deux mots de passe ne correspondent pas.")
        elif not user_obj and not pwd1:
            dj_messages.error(request, "Un mot de passe est requis à la création.")
        else:
            if pwd1:
                try:
                    validate_password(pwd1)
                except DjangoValidationError as e:
                    from django.contrib import messages as dj_messages
                    for err in e.messages:
                        dj_messages.error(request, err)
                    return render(request, "users/user_form.html", ctx)

            if user_obj:
                user_obj.username   = username
                user_obj.first_name = first_name
                user_obj.last_name  = last_name
                user_obj.email      = email
                user_obj.is_active  = actif
                if pwd1:
                    user_obj.set_password(pwd1)
                user_obj.save()
                target = user_obj
                action = "modification_user"
            else:
                target = User.objects.create_user(
                    username=username, email=email,
                    password=pwd1, first_name=first_name, last_name=last_name,
                    is_active=actif,
                )
                action = "creation_user"

            profil, _ = ProfilUtilisateur.objects.get_or_create(utilisateur=target)
            profil.poste     = poste
            profil.telephone = telephone
            profil.actif     = actif
            profil.role = Role.objects.get(pk=role_pk) if role_pk else None
            profil.save()

            journaliser(request, action,
                        f"Utilisateur {target.username} {'créé' if action == 'creation_user' else 'modifié'}",
                        objet_type="User", objet_id=target.pk)

            dj_messages.success(
                request,
                f"Utilisateur « {username} » {'créé' if action == 'creation_user' else 'modifié'} avec succès."
            )
            return redirect("dashboard:admin_utilisateurs")

    return render(request, "users/user_form.html", ctx)


@_admin_only
def vue_admin_user_toggle(request, pk):
    from django.contrib.auth.models import User
    from django.contrib import messages as dj_messages
    from apps.users.models import journaliser
    if request.method == "POST":
        try:
            u = User.objects.get(pk=pk)
            u.is_active = not u.is_active
            u.save()
            action = "activer" if u.is_active else "désactiver"
            dj_messages.success(request, f"Compte {u.username} {action}.")
            journaliser(request, "modification_user", f"Compte {u.username} {action}",
                        objet_type="User", objet_id=pk)
        except User.DoesNotExist:
            pass
    return redirect("dashboard:admin_utilisateurs")


@_admin_only
def vue_admin_journal(request):
    from apps.users.models import JournalAction
    from django.contrib.auth.models import User
    from django.core.paginator import Paginator

    today      = date.today()
    sept       = today - timedelta(days=7)
    type_sel   = request.GET.get("type_action", "")
    user_sel   = request.GET.get("user_id", "")
    succes_sel = request.GET.get("succes", "")
    date_debut = request.GET.get("date_debut", (today - timedelta(days=30)).isoformat())
    date_fin   = request.GET.get("date_fin",   today.isoformat())

    qs = JournalAction.objects.select_related("utilisateur").order_by("-date_action")
    if type_sel:
        qs = qs.filter(type_action=type_sel)
    if user_sel:
        qs = qs.filter(utilisateur__pk=user_sel)
    if succes_sel == "1":
        qs = qs.filter(succes=True)
    elif succes_sel == "0":
        qs = qs.filter(succes=False)
    try:
        qs = qs.filter(date_action__date__range=(date_debut, date_fin))
    except Exception:
        pass

    stats = {
        "total_7j":      JournalAction.objects.filter(date_action__date__gte=sept).count(),
        "erreurs_7j":    JournalAction.objects.filter(date_action__date__gte=sept, succes=False).count(),
        "connexions_7j": JournalAction.objects.filter(date_action__date__gte=sept, type_action="connexion").count(),
        "rapports_7j":   JournalAction.objects.filter(date_action__date__gte=sept, type_action="generation_rapport").count(),
    }

    paginator = Paginator(qs, 30)
    page_obj  = paginator.get_page(request.GET.get("page", 1))

    return render(request, "users/journal.html", {
        "page_obj":      page_obj,
        "types_action":  JournalAction.TypeAction.choices,
        "users_liste":   User.objects.filter(journal_actions__isnull=False).distinct(),
        "type_sel":      type_sel,
        "user_sel":      user_sel,
        "succes_sel":    succes_sel,
        "date_debut":    date_debut,
        "date_fin":      date_fin,
        "stats":         stats,
    })


@_admin_only
def vue_admin_seuils(request):
    from apps.kpi.models import SeuilAlerte, KPI
    seuils = SeuilAlerte.objects.select_related("kpi").order_by("kpi__categorie", "kpi__code")
    return render(request, "users/seuils.html", {
        "seuils":            seuils,
        "kpis_disponibles":  KPI.objects.all().order_by("categorie", "libelle"),
    })


@_admin_only
def vue_admin_seuils_sauver(request):
    from apps.kpi.models import SeuilAlerte
    from django.contrib import messages as dj_messages
    from apps.users.models import journaliser
    if request.method == "POST":
        seuils = SeuilAlerte.objects.all()
        for s in seuils:
            vmin = request.POST.get(f"min_{s.pk}", "").strip()
            vmax = request.POST.get(f"max_{s.pk}", "").strip()
            grav = request.POST.get(f"gravite_{s.pk}", s.niveau_gravite)
            s.valeur_min    = float(vmin) if vmin else None
            s.valeur_max    = float(vmax) if vmax else None
            s.niveau_gravite = grav
            s.save()
        journaliser(request, "modification_seuil", f"{seuils.count()} seuil(s) mis à jour")
        dj_messages.success(request, "Seuils enregistrés avec succès.")
    return redirect("dashboard:admin_seuils")


@_admin_only
def vue_admin_seuil_ajouter(request):
    from apps.kpi.models import SeuilAlerte, KPI
    from django.contrib import messages as dj_messages
    if request.method == "POST":
        kpi_pk = request.POST.get("kpi")
        vmin   = request.POST.get("valeur_min", "").strip()
        vmax   = request.POST.get("valeur_max", "").strip()
        grav   = request.POST.get("niveau_gravite", "avertissement")
        try:
            kpi = KPI.objects.get(pk=kpi_pk)
            SeuilAlerte.objects.create(
                kpi=kpi,
                valeur_min=float(vmin) if vmin else None,
                valeur_max=float(vmax) if vmax else None,
                niveau_gravite=grav,
            )
            dj_messages.success(request, f"Seuil ajouté pour « {kpi.libelle} ».")
        except Exception as exc:
            dj_messages.error(request, f"Erreur : {exc}")
    return redirect("dashboard:admin_seuils")


@_admin_only
def vue_admin_seuil_supprimer(request, pk):
    from apps.kpi.models import SeuilAlerte
    from django.contrib import messages as dj_messages
    try:
        s = SeuilAlerte.objects.get(pk=pk)
        nom = str(s)
        s.delete()
        dj_messages.success(request, f"Seuil « {nom} » supprimé.")
    except SeuilAlerte.DoesNotExist:
        pass
    return redirect("dashboard:admin_seuils")

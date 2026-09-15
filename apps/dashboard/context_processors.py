"""
Context processor : injecte le nombre d'alertes actives dans tous les templates
pour afficher le badge dans la sidebar, ainsi que le rôle de l'utilisateur connecté.
"""


def alertes_badge(request):
    if not request.user.is_authenticated:
        return {}
    try:
        from apps.alerts.models import Alerte
        qs = Alerte.objects.filter(statut="active")
        ctx = {
            "nb_alertes_actives": qs.count(),
            "nb_critiques": qs.filter(niveau_gravite="critique").count(),
        }
    except Exception:
        ctx = {"nb_alertes_actives": 0, "nb_critiques": 0}

    # Rôle de l'utilisateur connecté (pour conditionner la navigation)
    try:
        profil = request.user.profil
        ctx["user_role"] = profil.role.code if profil.role else ""
        ctx["user_is_dapc"] = ctx["user_role"] == "dapc"
    except Exception:
        ctx["user_role"] = ""
        ctx["user_is_dapc"] = False

    # Administrateur : is_staff, is_superuser, ou rôle admin via profil
    is_admin = (
        request.user.is_staff
        or request.user.is_superuser
        or ctx["user_role"] == "admin"
    )
    if is_admin:
        ctx["user_role"] = "admin"
        ctx["user_is_dapc"] = False
    ctx["user_is_admin"] = is_admin

    return ctx

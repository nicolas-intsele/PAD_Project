"""
Context processor : injecte le nombre d'alertes actives dans tous les templates
pour afficher le badge dans la sidebar.
"""


def alertes_badge(request):
    if not request.user.is_authenticated:
        return {}
    try:
        from apps.alerts.models import Alerte
        qs = Alerte.objects.filter(statut="active")
        return {
            "nb_alertes_actives": qs.count(),
            "nb_critiques": qs.filter(niveau_gravite="critique").count(),
        }
    except Exception:
        return {"nb_alertes_actives": 0, "nb_critiques": 0}

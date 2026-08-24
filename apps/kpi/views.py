from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .engine.service import calculer_kpi_mois
from .models import KPI, SeuilAlerte, ValeurKPI
from .serializers import KPISerializer, SeuilAlerteSerializer, ValeurKPISerializer


class KPIViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/kpi/definitions/ — catalogue des 13 KPI (Module 3)."""

    queryset = KPI.objects.all()
    serializer_class = KPISerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        categorie = self.request.query_params.get("categorie")
        if categorie:
            qs = qs.filter(categorie=categorie)
        return qs


class ValeurKPIViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/kpi/valeurs/?categorie=temps&annee=2026&mois=3
    Consultation des valeurs de KPI historisées, filtrables par catégorie et période.
    """

    queryset = ValeurKPI.objects.select_related("kpi", "date_ref").all()
    serializer_class = ValeurKPISerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        categorie = self.request.query_params.get("categorie")
        code = self.request.query_params.get("code")
        annee = self.request.query_params.get("annee")
        mois = self.request.query_params.get("mois")
        if categorie:
            qs = qs.filter(kpi__categorie=categorie)
        if code:
            qs = qs.filter(kpi__code=code)
        if annee:
            qs = qs.filter(date_ref__annee=annee)
        if mois:
            qs = qs.filter(date_ref__mois=mois)
        return qs

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def recalculer(self, request):
        """POST /api/kpi/valeurs/recalculer/  {"annee": 2026, "mois": 3}"""
        try:
            annee = int(request.data["annee"])
            mois = int(request.data["mois"])
        except (KeyError, ValueError, TypeError):
            return Response({"detail": "Paramètres 'annee' et 'mois' requis (entiers)."}, status=400)

        resultats = calculer_kpi_mois(annee, mois)
        return Response({"periode": f"{annee}-{mois:02d}", "resultats": resultats})


class SeuilAlerteViewSet(viewsets.ModelViewSet):
    """CRUD des seuils d'alerte (paramétrage — Module 8). Écriture réservée aux admins."""

    queryset = SeuilAlerte.objects.select_related("kpi").all()
    serializer_class = SeuilAlerteSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]
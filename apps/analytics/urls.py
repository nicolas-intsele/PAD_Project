"""
URLs du module d'analyse multidimensionnelle.
Préfixe : /api/analytics/
"""
from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    CubeAnalyseViewSet,
    ClassementView,
    ComparaisonView,
    CorrelationView,
    ExectuterCubeView,
    HeatmapOccupationView,
    RepartitionStatutsView,
    SyntheseView,
    TendanceView,
    liste_axes,
    liste_mesures,
)

router = SimpleRouter()
router.register("cubes", CubeAnalyseViewSet, basename="cube-analyse")

urlpatterns = [
    # Référentiel OLAP
    path("axes/", liste_axes, name="analytics-axes"),
    path("mesures/", liste_mesures, name="analytics-mesures"),

    # Catalogue et exécution de cubes
    path("", include(router.urls)),
    path("cube/executer/", ExectuterCubeView.as_view(), name="analytics-cube-executer"),

    # Analyses avancées
    path("tendance/", TendanceView.as_view(), name="analytics-tendance"),
    path("comparaison/", ComparaisonView.as_view(), name="analytics-comparaison"),
    path("classement/", ClassementView.as_view(), name="analytics-classement"),
    path("correlation/", CorrelationView.as_view(), name="analytics-correlation"),
    path("synthese/", SyntheseView.as_view(), name="analytics-synthese"),
    path("heatmap-occupation/", HeatmapOccupationView.as_view(), name="analytics-heatmap"),
    path("repartition-statuts/", RepartitionStatutsView.as_view(), name="analytics-repartition-statuts"),
]

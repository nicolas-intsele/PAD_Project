from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import KPIViewSet, SeuilAlerteViewSet, ValeurKPIViewSet

router = SimpleRouter()
router.register("definitions", KPIViewSet, basename="kpi-definition")
router.register("valeurs", ValeurKPIViewSet, basename="kpi-valeur")
router.register("seuils", SeuilAlerteViewSet, basename="kpi-seuil")

urlpatterns = [
    path("", include(router.urls)),
]
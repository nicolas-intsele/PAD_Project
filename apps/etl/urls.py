from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ImportFichierView, JournalImportViewSet

router = DefaultRouter()
router.register("imports", JournalImportViewSet, basename="journal-import")

urlpatterns = [
    path("import/", ImportFichierView.as_view(), name="etl-import"),
    path("", include(router.urls)),
]

from rest_framework import permissions, status, viewsets
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import JournalImport
from .registre_pad.service import run_import_registre_pad
from .serializers import ImportUploadSerializer, JournalImportSerializer
from .services import run_import


class JournalImportViewSet(viewsets.ReadOnlyModelViewSet):
    """Consultation de l'historique des imports (lecture seule)."""

    queryset = JournalImport.objects.all()
    serializer_class = JournalImportSerializer
    permission_classes = [permissions.IsAuthenticated]


class ImportFichierView(APIView):
    """
    POST /api/etl/import/
    Déclenche le pipeline ETL complet pour un fichier CSV ou Excel envoyé en multipart/form-data.
    Réservé aux administrateurs (Module 8 — Administration).
    """

    parser_classes = [MultiPartParser]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = ImportUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fichier = serializer.validated_data["fichier"]
        format_fichier = serializer.validated_data["format"]

        if format_fichier == "registre_pad":
            resultat = run_import_registre_pad(fichier, source_name=fichier.name, utilisateur=request.user)
        else:
            resultat = run_import(
                fichier, source_name=fichier.name, format=format_fichier, utilisateur=request.user
            )

        payload = JournalImportSerializer(resultat.journal).data
        http_status = status.HTTP_201_CREATED if resultat.reussi else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(payload, status=http_status)

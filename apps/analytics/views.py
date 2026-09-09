"""
Vues API du module d'analyse multidimensionnelle (Module 4).

Endpoints :
  GET  /api/analytics/axes/                        — liste des axes disponibles
  GET  /api/analytics/mesures/                     — liste des mesures disponibles
  GET  /api/analytics/cubes/                       — catalogue des cubes définis
  POST /api/analytics/cube/executer/               — exécuter un cube ad hoc
  GET  /api/analytics/tendance/?mesure=&...        — tendance temporelle + régression
  GET  /api/analytics/comparaison/?mesure=&...     — delta entre deux périodes
  GET  /api/analytics/classement/?mesure=&...      — top-N par axe
  GET  /api/analytics/correlation/?mesure_x=&...   — corrélation Pearson
  GET  /api/analytics/synthese/?date_debut=&...    — synthèse globale d'une période
  GET  /api/analytics/heatmap-occupation/?...      — heatmap quais × semaines
  GET  /api/analytics/repartition-statuts/?...     — distribution par statut
"""
from __future__ import annotations

import logging

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .analyses import (
    analyser_correlation,
    calculer_tendance,
    classement,
    comparer_periodes,
    heatmap_occupation,
    repartition_statut,
    synthese_periode,
)
from .cube import MoteurCube
from .models import AxeAnalyse, CubeAnalyse, ResultatCube
from .serializers import (
    AxeAnalyseSerializer,
    CubeAnalyseSerializer,
    ParametresClassementSerializer,
    ParametresComparaisonSerializer,
    ParametresCorrelationSerializer,
    ParametresCubeSerializer,
    ParametresHeatmapSerializer,
    ParametresSyntheseSerializer,
    ParametresTendanceSerializer,
    ResultatCubeSerializer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Référentiel (axes et mesures disponibles)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def liste_axes(request):
    """GET /api/analytics/axes/ — retourne les 9 axes d'analyse disponibles."""
    axes = [
        {"code": code, "libelle": label}
        for code, label in AxeAnalyse.Type.choices
    ]
    return Response(axes)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def liste_mesures(request):
    """GET /api/analytics/mesures/ — retourne les 11 mesures disponibles."""
    mesures = [
        {"code": code, "libelle": label}
        for code, label in CubeAnalyse.Mesure.choices
    ]
    return Response(mesures)


# ─────────────────────────────────────────────────────────────────────────────
# Catalogue de cubes sauvegardés
# ─────────────────────────────────────────────────────────────────────────────

class CubeAnalyseViewSet(viewsets.ModelViewSet):
    """
    CRUD des cubes d'analyse sauvegardés.
    Lecture libre, écriture réservée aux admins.
    """

    queryset = CubeAnalyse.objects.select_related("axe_ligne", "axe_colonne").filter(actif=True)
    serializer_class = CubeAnalyseSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]


# ─────────────────────────────────────────────────────────────────────────────
# Exécution ad hoc d'un cube
# ─────────────────────────────────────────────────────────────────────────────

class ExectuterCubeView(APIView):
    """
    POST /api/analytics/cube/executer/

    Body JSON ::

        {
          "mesure": "nb_escales",
          "axe_ligne": "terminal",
          "axe_colonne": "temps_mois",   // optionnel
          "date_debut": "2026-01-01",
          "date_fin": "2026-06-30",
          "format": "plat"               // "plat" | "pivot" | "resume"
        }

    Retourne le résultat calculé + un résumé statistique.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ser = ParametresCubeSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        params = ser.validated_data
        try:
            moteur = MoteurCube(
                mesure=params["mesure"],
                axe_ligne=params["axe_ligne"],
                axe_colonne=params.get("axe_colonne"),
                date_debut=params["date_debut"],
                date_fin=params["date_fin"],
            )

            fmt = params.get("format", "plat")
            if fmt == "pivot":
                donnees = moteur.calculer_pivot()
            elif fmt == "resume":
                donnees = moteur.calculer_resume()
            else:
                donnees = moteur.calculer_plat()

            resume = moteur.calculer_resume() if fmt != "resume" else donnees

            return Response({
                "parametres": {
                    "mesure": params["mesure"],
                    "axe_ligne": params["axe_ligne"],
                    "axe_colonne": params.get("axe_colonne"),
                    "date_debut": params["date_debut"].isoformat(),
                    "date_fin": params["date_fin"].isoformat(),
                    "format": fmt,
                },
                "resultats": donnees,
                "resume": resume if fmt != "resume" else None,
            })

        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Erreur exécution cube ad hoc")
            return Response(
                {"detail": "Erreur interne lors du calcul."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Analyses avancées
# ─────────────────────────────────────────────────────────────────────────────

class TendanceView(APIView):
    """
    GET /api/analytics/tendance/
    ?mesure=nb_escales&date_debut=2026-01-01&date_fin=2026-06-30&granularite=mois
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ser = ParametresTendanceSerializer(data=request.query_params)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        p = ser.validated_data
        try:
            result = calculer_tendance(
                mesure=p["mesure"],
                date_debut=p["date_debut"],
                date_fin=p["date_fin"],
                granularite=p.get("granularite", "mois"),
            )
            return Response(result)
        except Exception as exc:
            logger.exception("Erreur calcul tendance")
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ComparaisonView(APIView):
    """
    GET /api/analytics/comparaison/
    ?mesure=nb_escales&axe=terminal
    &ref_debut=2025-01-01&ref_fin=2025-12-31
    &comp_debut=2026-01-01&comp_fin=2026-06-30
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ser = ParametresComparaisonSerializer(data=request.query_params)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        p = ser.validated_data
        try:
            result = comparer_periodes(
                mesure=p["mesure"],
                axe=p["axe"],
                periode_ref_debut=p["ref_debut"],
                periode_ref_fin=p["ref_fin"],
                periode_comp_debut=p["comp_debut"],
                periode_comp_fin=p["comp_fin"],
            )
            return Response({
                "periode_reference": {"debut": p["ref_debut"].isoformat(), "fin": p["ref_fin"].isoformat()},
                "periode_comparaison": {"debut": p["comp_debut"].isoformat(), "fin": p["comp_fin"].isoformat()},
                "mesure": p["mesure"],
                "axe": p["axe"],
                "comparaison": result,
            })
        except Exception as exc:
            logger.exception("Erreur calcul comparaison")
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClassementView(APIView):
    """
    GET /api/analytics/classement/
    ?mesure=nb_escales&axe=terminal
    &date_debut=2026-01-01&date_fin=2026-06-30
    &top=10&ordre=desc
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ser = ParametresClassementSerializer(data=request.query_params)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        p = ser.validated_data
        try:
            result = classement(
                mesure=p["mesure"],
                axe=p["axe"],
                date_debut=p["date_debut"],
                date_fin=p["date_fin"],
                top=p.get("top", 10),
                ordre=p.get("ordre", "desc"),
            )
            return Response({
                "mesure": p["mesure"],
                "axe": p["axe"],
                "periode": {
                    "debut": p["date_debut"].isoformat(),
                    "fin": p["date_fin"].isoformat(),
                },
                "classement": result,
            })
        except Exception as exc:
            logger.exception("Erreur calcul classement")
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CorrelationView(APIView):
    """
    GET /api/analytics/correlation/
    ?mesure_x=nb_escales&mesure_y=temps_attente_moy
    &date_debut=2026-01-01&date_fin=2026-06-30
    &granularite=mois
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ser = ParametresCorrelationSerializer(data=request.query_params)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        p = ser.validated_data
        try:
            result = analyser_correlation(
                mesure_x=p["mesure_x"],
                mesure_y=p["mesure_y"],
                date_debut=p["date_debut"],
                date_fin=p["date_fin"],
                granularite=p.get("granularite", "mois"),
            )
            return Response(result)
        except Exception as exc:
            logger.exception("Erreur calcul corrélation")
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SyntheseView(APIView):
    """
    GET /api/analytics/synthese/
    ?date_debut=2026-01-01&date_fin=2026-06-30
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ser = ParametresSyntheseSerializer(data=request.query_params)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        p = ser.validated_data
        try:
            result = synthese_periode(
                date_debut=p["date_debut"],
                date_fin=p["date_fin"],
            )
            return Response(result)
        except Exception as exc:
            logger.exception("Erreur calcul synthèse")
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HeatmapOccupationView(APIView):
    """
    GET /api/analytics/heatmap-occupation/
    ?date_debut=2026-01-01&date_fin=2026-06-30
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ser = ParametresHeatmapSerializer(data=request.query_params)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        p = ser.validated_data
        try:
            result = heatmap_occupation(
                date_debut=p["date_debut"],
                date_fin=p["date_fin"],
            )
            return Response(result)
        except Exception as exc:
            logger.exception("Erreur calcul heatmap")
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RepartitionStatutsView(APIView):
    """
    GET /api/analytics/repartition-statuts/
    ?date_debut=2026-01-01&date_fin=2026-06-30
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ser = ParametresHeatmapSerializer(data=request.query_params)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        p = ser.validated_data
        try:
            result = repartition_statut(
                date_debut=p["date_debut"],
                date_fin=p["date_fin"],
            )
            return Response({
                "periode": {
                    "debut": p["date_debut"].isoformat(),
                    "fin": p["date_fin"].isoformat(),
                },
                "repartition": result,
            })
        except Exception as exc:
            logger.exception("Erreur répartition statuts")
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

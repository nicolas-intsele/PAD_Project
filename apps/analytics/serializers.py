"""
Serializers du module d'analyse multidimensionnelle.
"""
from __future__ import annotations

from datetime import date

from rest_framework import serializers

from .models import AxeAnalyse, CubeAnalyse, ResultatCube


class AxeAnalyseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AxeAnalyse
        fields = ["code", "libelle", "description", "actif"]


class CubeAnalyseSerializer(serializers.ModelSerializer):
    axe_ligne_code = serializers.CharField(source="axe_ligne.code", read_only=True)
    axe_ligne_libelle = serializers.CharField(source="axe_ligne.libelle", read_only=True)
    axe_colonne_code = serializers.CharField(source="axe_colonne.code", read_only=True, allow_null=True)
    axe_colonne_libelle = serializers.CharField(source="axe_colonne.libelle", read_only=True, allow_null=True)
    mesure_libelle = serializers.CharField(source="get_mesure_display", read_only=True)

    class Meta:
        model = CubeAnalyse
        fields = [
            "id", "nom", "description", "mesure", "mesure_libelle",
            "axe_ligne", "axe_ligne_code", "axe_ligne_libelle",
            "axe_colonne", "axe_colonne_code", "axe_colonne_libelle",
            "actif", "date_creation",
        ]


class ResultatCubeSerializer(serializers.ModelSerializer):
    cube_nom = serializers.CharField(source="cube.nom", read_only=True)

    class Meta:
        model = ResultatCube
        fields = [
            "id", "cube", "cube_nom", "annee", "mois_debut", "mois_fin",
            "donnees", "nb_lignes", "date_calcul",
        ]


# ── Serializers de paramètres d'entrée (validation des requêtes) ──────────────

class ParametresCubeSerializer(serializers.Serializer):
    """Paramètres pour POST /api/analytics/cube/executer/"""

    mesure = serializers.ChoiceField(choices=CubeAnalyse.Mesure.choices)
    axe_ligne = serializers.ChoiceField(choices=AxeAnalyse.Type.choices)
    axe_colonne = serializers.ChoiceField(
        choices=AxeAnalyse.Type.choices, required=False, allow_null=True
    )
    date_debut = serializers.DateField()
    date_fin = serializers.DateField()
    format = serializers.ChoiceField(
        choices=[("plat", "Plat"), ("pivot", "Pivot"), ("resume", "Résumé")],
        default="plat",
    )

    def validate(self, data):
        if data["date_debut"] > data["date_fin"]:
            raise serializers.ValidationError("date_debut doit être ≤ date_fin.")
        if data.get("axe_colonne") == data["axe_ligne"]:
            raise serializers.ValidationError("axe_ligne et axe_colonne doivent être différents.")
        if data.get("format") == "pivot" and not data.get("axe_colonne"):
            raise serializers.ValidationError("Le format 'pivot' nécessite un axe_colonne.")
        return data


class ParametresTendanceSerializer(serializers.Serializer):
    """Paramètres pour GET /api/analytics/tendance/"""

    mesure = serializers.ChoiceField(choices=CubeAnalyse.Mesure.choices)
    date_debut = serializers.DateField()
    date_fin = serializers.DateField()
    granularite = serializers.ChoiceField(
        choices=[("mois", "Mois"), ("trimestre", "Trimestre"), ("annee", "Année")],
        default="mois",
    )

    def validate(self, data):
        if data["date_debut"] > data["date_fin"]:
            raise serializers.ValidationError("date_debut doit être ≤ date_fin.")
        return data


class ParametresComparaisonSerializer(serializers.Serializer):
    """Paramètres pour GET /api/analytics/comparaison/"""

    mesure = serializers.ChoiceField(choices=CubeAnalyse.Mesure.choices)
    axe = serializers.ChoiceField(choices=AxeAnalyse.Type.choices)
    ref_debut = serializers.DateField()
    ref_fin = serializers.DateField()
    comp_debut = serializers.DateField()
    comp_fin = serializers.DateField()

    def validate(self, data):
        if data["ref_debut"] > data["ref_fin"]:
            raise serializers.ValidationError("ref_debut doit être ≤ ref_fin.")
        if data["comp_debut"] > data["comp_fin"]:
            raise serializers.ValidationError("comp_debut doit être ≤ comp_fin.")
        return data


class ParametresClassementSerializer(serializers.Serializer):
    """Paramètres pour GET /api/analytics/classement/"""

    mesure = serializers.ChoiceField(choices=CubeAnalyse.Mesure.choices)
    axe = serializers.ChoiceField(choices=AxeAnalyse.Type.choices)
    date_debut = serializers.DateField()
    date_fin = serializers.DateField()
    top = serializers.IntegerField(min_value=1, max_value=50, default=10)
    ordre = serializers.ChoiceField(
        choices=[("desc", "Top (meilleurs)"), ("asc", "Flop (moins bons)")],
        default="desc",
    )

    def validate(self, data):
        if data["date_debut"] > data["date_fin"]:
            raise serializers.ValidationError("date_debut doit être ≤ date_fin.")
        return data


class ParametresCorrelationSerializer(serializers.Serializer):
    """Paramètres pour GET /api/analytics/correlation/"""

    mesure_x = serializers.ChoiceField(choices=CubeAnalyse.Mesure.choices)
    mesure_y = serializers.ChoiceField(choices=CubeAnalyse.Mesure.choices)
    date_debut = serializers.DateField()
    date_fin = serializers.DateField()
    granularite = serializers.ChoiceField(
        choices=[("mois", "Mois"), ("trimestre", "Trimestre"), ("annee", "Année")],
        default="mois",
    )

    def validate(self, data):
        if data["date_debut"] > data["date_fin"]:
            raise serializers.ValidationError("date_debut doit être ≤ date_fin.")
        if data["mesure_x"] == data["mesure_y"]:
            raise serializers.ValidationError("mesure_x et mesure_y doivent être différentes.")
        return data


class ParametresSyntheseSerializer(serializers.Serializer):
    """Paramètres pour GET /api/analytics/synthese/"""

    date_debut = serializers.DateField()
    date_fin = serializers.DateField()

    def validate(self, data):
        if data["date_debut"] > data["date_fin"]:
            raise serializers.ValidationError("date_debut doit être ≤ date_fin.")
        return data


class ParametresHeatmapSerializer(serializers.Serializer):
    """Paramètres pour GET /api/analytics/heatmap-occupation/"""

    date_debut = serializers.DateField()
    date_fin = serializers.DateField()

    def validate(self, data):
        if data["date_debut"] > data["date_fin"]:
            raise serializers.ValidationError("date_debut doit être ≤ date_fin.")
        return data

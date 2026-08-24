from rest_framework import serializers

from .models import KPI, SeuilAlerte, ValeurKPI


class KPISerializer(serializers.ModelSerializer):
    class Meta:
        model = KPI
        fields = ["id_kpi", "code", "libelle", "categorie", "unite", "formule"]


class ValeurKPISerializer(serializers.ModelSerializer):
    kpi_code = serializers.CharField(source="kpi.code", read_only=True)
    kpi_libelle = serializers.CharField(source="kpi.libelle", read_only=True)
    categorie = serializers.CharField(source="kpi.categorie", read_only=True)
    unite = serializers.CharField(source="kpi.unite", read_only=True)
    periode = serializers.DateField(source="date_ref.date_calendaire", read_only=True)

    class Meta:
        model = ValeurKPI
        fields = ["id_valeur", "kpi_code", "kpi_libelle", "categorie", "unite", "periode", "valeur", "date_calcul"]


class SeuilAlerteSerializer(serializers.ModelSerializer):
    kpi_code = serializers.CharField(source="kpi.code", read_only=True)

    class Meta:
        model = SeuilAlerte
        fields = ["id_seuil", "kpi", "kpi_code", "valeur_min", "valeur_max", "niveau_gravite"]
"""
Interface d'administration Django pour le module d'analyse multidimensionnelle.
"""
from django.contrib import admin

from .models import AxeAnalyse, CubeAnalyse, ResultatCube


@admin.register(AxeAnalyse)
class AxeAnalyseAdmin(admin.ModelAdmin):
    list_display = ["code", "libelle", "actif"]
    list_filter = ["actif"]
    search_fields = ["code", "libelle"]


@admin.register(CubeAnalyse)
class CubeAnalyseAdmin(admin.ModelAdmin):
    list_display = ["nom", "mesure", "axe_ligne", "axe_colonne", "actif", "date_creation"]
    list_filter = ["mesure", "actif"]
    search_fields = ["nom", "description"]
    autocomplete_fields = ["axe_ligne", "axe_colonne"]
    readonly_fields = ["date_creation"]


@admin.register(ResultatCube)
class ResultatCubeAdmin(admin.ModelAdmin):
    list_display = ["cube", "annee", "mois_debut", "mois_fin", "nb_lignes", "date_calcul"]
    list_filter = ["annee", "cube"]
    readonly_fields = ["date_calcul", "nb_lignes", "donnees"]
    date_hierarchy = "date_calcul"

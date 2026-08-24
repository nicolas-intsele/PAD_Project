from django.contrib import admin

from .models import KPI, SeuilAlerte, ValeurKPI


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle", "categorie", "unite")
    list_filter = ("categorie",)
    search_fields = ("code", "libelle")


@admin.register(ValeurKPI)
class ValeurKPIAdmin(admin.ModelAdmin):
    list_display = ("kpi", "date_ref", "valeur", "date_calcul")
    list_filter = ("kpi__categorie", "kpi")
    date_hierarchy = "date_calcul"


@admin.register(SeuilAlerte)
class SeuilAlerteAdmin(admin.ModelAdmin):
    list_display = ("kpi", "valeur_min", "valeur_max", "niveau_gravite")
    list_filter = ("niveau_gravite",)
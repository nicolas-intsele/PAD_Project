from django.contrib import admin
from .models import Rapport, RapportKPI


class RapportKPIInline(admin.TabularInline):
    model = RapportKPI
    extra = 0


@admin.register(Rapport)
class RapportAdmin(admin.ModelAdmin):
    list_display  = ["type_rapport", "periode_debut", "periode_fin", "format", "taille_lisible", "date_generation", "utilisateur"]
    list_filter   = ["type_rapport", "format"]
    date_hierarchy = "date_generation"
    readonly_fields = ["date_generation", "taille_octets", "nb_pages"]
    inlines = [RapportKPIInline]

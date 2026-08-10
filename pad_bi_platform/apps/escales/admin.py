from django.contrib import admin

from .models import Escale, Mobiliser


class MobiliserInline(admin.TabularInline):
    model = Mobiliser
    extra = 0


@admin.register(Escale)
class EscaleAdmin(admin.ModelAdmin):
    list_display = ("navire", "quai", "date_arrivee", "date_depart", "temps_attente", "temps_sejour", "statut")
    list_filter = ("statut", "quai__terminal", "quai")
    search_fields = ("navire__nom", "navire__imo")
    date_hierarchy = "date_arrivee"
    inlines = [MobiliserInline]

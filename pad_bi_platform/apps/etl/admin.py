from django.contrib import admin

from .models import JournalImport


@admin.register(JournalImport)
class JournalImportAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "date_import", "statut", "nb_lignes_lues", "nb_lignes_chargees", "nb_lignes_rejetees")
    list_filter = ("statut",)
    search_fields = ("source",)
    readonly_fields = [f.name for f in JournalImport._meta.fields]

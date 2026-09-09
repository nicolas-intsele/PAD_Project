from django.contrib import admin
from .models import Alerte, UtilisateurAlerte


@admin.register(Alerte)
class AlerteAdmin(admin.ModelAdmin):
    list_display  = ["type_alerte", "niveau_gravite", "message_court", "statut", "date_declenchement"]
    list_filter   = ["statut", "niveau_gravite", "type_alerte"]
    search_fields = ["message"]
    date_hierarchy = "date_declenchement"
    readonly_fields = ["date_declenchement", "date_resolution", "valeur_declenchante"]
    actions = ["acquitter", "resoudre"]

    def message_court(self, obj):
        return obj.message[:80] + "…" if len(obj.message) > 80 else obj.message
    message_court.short_description = "Message"

    @admin.action(description="Acquitter les alertes sélectionnées")
    def acquitter(self, request, queryset):
        for a in queryset:
            a.acquitter(request.user)
        self.message_user(request, f"{queryset.count()} alerte(s) acquittée(s).")

    @admin.action(description="Marquer comme résolues")
    def resoudre(self, request, queryset):
        for a in queryset:
            a.resoudre()
        self.message_user(request, f"{queryset.count()} alerte(s) résolue(s).")


@admin.register(UtilisateurAlerte)
class UtilisateurAlerteAdmin(admin.ModelAdmin):
    list_display = ["utilisateur", "alerte", "statut_lecture", "date_lecture"]
    list_filter  = ["statut_lecture"]

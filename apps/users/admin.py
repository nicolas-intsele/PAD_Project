from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Role, ProfilUtilisateur, JournalAction


class ProfilInline(admin.StackedInline):
    model = ProfilUtilisateur
    can_delete = False
    verbose_name_plural = "Profil"
    fields = ["role", "telephone", "poste", "actif"]


class UserAdmin(BaseUserAdmin):
    inlines = [ProfilInline]
    list_display  = ["username", "get_full_name", "email", "get_role", "is_active", "last_login"]
    list_filter   = ["is_active", "is_staff", "profil__role"]

    def get_role(self, obj):
        try:
            return obj.profil.role.libelle if obj.profil.role else "—"
        except Exception:
            return "—"
    get_role.short_description = "Rôle"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["code", "libelle", "permissions_kpi", "permissions_analytics",
                    "permissions_reporting", "permissions_admin"]
    list_editable = ["permissions_kpi", "permissions_analytics",
                     "permissions_reporting", "permissions_admin"]


@admin.register(JournalAction)
class JournalActionAdmin(admin.ModelAdmin):
    list_display  = ["date_action", "utilisateur", "type_action", "description_courte", "succes", "ip_address"]
    list_filter   = ["type_action", "succes"]
    search_fields = ["utilisateur__username", "description"]
    date_hierarchy = "date_action"
    readonly_fields = ["date_action", "utilisateur", "ip_address", "type_action",
                       "description", "succes", "objet_type", "objet_id"]

    def description_courte(self, obj):
        return obj.description[:70] + "…" if len(obj.description) > 70 else obj.description
    description_courte.short_description = "Description"

    def has_add_permission(self, request):
        return False

from django.contrib import admin

from .models import AgentMaritime, Calendrier, CompagnieMaritime, Navire, Quai, ServiceNautique, Terminal, TypeNavire

admin.site.register(TypeNavire)
admin.site.register(CompagnieMaritime)
admin.site.register(Terminal)
admin.site.register(AgentMaritime)
admin.site.register(ServiceNautique)
admin.site.register(Calendrier)


@admin.register(Quai)
class QuaiAdmin(admin.ModelAdmin):
    list_display = ("nom", "terminal", "longueur", "tirant_eau_max")
    list_filter = ("terminal",)


@admin.register(Navire)
class NavireAdmin(admin.ModelAdmin):
    list_display = ("nom", "imo", "type_navire", "compagnie", "pavillon")
    search_fields = ("nom", "imo")
    list_filter = ("type_navire", "compagnie")

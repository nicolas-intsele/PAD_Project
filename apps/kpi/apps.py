from django.apps import AppConfig


class KpiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.kpi"
    verbose_name = "KPI - Calcul automatique des indicateurs de performance"
"""
Management command — lance le scan complet des alertes.
Usage :
    python manage.py scanner_alertes
    python manage.py scanner_alertes --date-debut 2026-01-01 --date-fin 2026-06-30
"""
from datetime import date
from django.core.management.base import BaseCommand
from apps.alerts.service import scanner_alertes


class Command(BaseCommand):
    help = "Scan et création des alertes (KPI hors seuil + escales critiques)"

    def add_arguments(self, parser):
        parser.add_argument("--date-debut", type=str, default=None)
        parser.add_argument("--date-fin",   type=str, default=None)

    def handle(self, *args, **options):
        d_deb = date.fromisoformat(options["date_debut"]) if options["date_debut"] else None
        d_fin = date.fromisoformat(options["date_fin"])   if options["date_fin"]   else None
        result = scanner_alertes(d_deb, d_fin)
        self.stdout.write(self.style.SUCCESS(
            f"Scan terminé : {result['total']} alerte(s) créée(s) "
            f"(KPI: {result['alertes_kpi']}, escales: {result['alertes_escales']})"
        ))

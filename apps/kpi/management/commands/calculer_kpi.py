from django.core.management.base import BaseCommand

from apps.kpi.engine.service import calculer_kpi_mois, calculer_toutes_les_periodes, mois_disponibles


class Command(BaseCommand):
    help = "Calcule et historise les KPI (Module 3) pour un mois donné, ou pour toutes les périodes disponibles."

    def add_arguments(self, parser):
        parser.add_argument("--annee", type=int, help="Année (ex. 2026)")
        parser.add_argument("--mois", type=int, help="Mois (1-12)")
        parser.add_argument("--tout", action="store_true", help="Recalculer tous les mois où des escales existent")

    def handle(self, *args, **options):
        if options["tout"]:
            disponibles = mois_disponibles()
            if not disponibles:
                self.stdout.write(self.style.WARNING("Aucune escale en base : rien à calculer."))
                return
            self.stdout.write(f"Calcul des KPI pour {len(disponibles)} période(s)...")
            resultats = calculer_toutes_les_periodes()
            for periode, valeurs in resultats.items():
                self._afficher(periode, valeurs)
            return

        if not options["annee"] or not options["mois"]:
            self.stdout.write(self.style.ERROR("Précisez --annee et --mois, ou utilisez --tout."))
            return

        valeurs = calculer_kpi_mois(options["annee"], options["mois"])
        self._afficher(f"{options['annee']}-{options['mois']:02d}", valeurs)

    def _afficher(self, periode, valeurs):
        self.stdout.write(self.style.SUCCESS(f"\n=== {periode} ==="))
        for code, valeur in valeurs.items():
            affichage = f"{valeur}" if valeur is not None else "n/a (aucune donnée)"
            self.stdout.write(f"  {code:<28} {affichage}")
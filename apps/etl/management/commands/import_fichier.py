from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.etl.services import run_import


class Command(BaseCommand):
    help = "Importe un fichier CSV ou Excel d'escales (gabarit générique) dans la base décisionnelle."

    def add_arguments(self, parser):
        parser.add_argument("chemin_fichier", type=str, help="Chemin du fichier CSV/Excel à importer")
        parser.add_argument(
            "--format", type=str, choices=["csv", "excel"], default=None,
            help="Format du fichier (déduit automatiquement de l'extension si omis)",
        )

    def handle(self, *args, **options):
        chemin = Path(options["chemin_fichier"])
        if not chemin.exists():
            raise CommandError(f"Fichier introuvable : {chemin}")

        format_fichier = options["format"] or ("excel" if chemin.suffix.lower() in (".xlsx", ".xls") else "csv")

        self.stdout.write(f"Import de {chemin.name} ({format_fichier})...")
        resultat = run_import(str(chemin), source_name=chemin.name, format=format_fichier)

        journal = resultat.journal
        self.stdout.write(self.style.SUCCESS(f"Journal d'import #{journal.pk} — statut : {journal.statut}"))
        self.stdout.write(f"  Lignes lues     : {journal.nb_lignes_lues}")
        self.stdout.write(f"  Lignes chargées : {journal.nb_lignes_chargees}")
        self.stdout.write(f"  Lignes rejetées : {journal.nb_lignes_rejetees}")
        self.stdout.write(f"  {resultat.rapport_qualite.summary()}")

        if journal.erreurs:
            self.stdout.write(self.style.WARNING("Détail des anomalies :"))
            for err in journal.erreurs[:20]:
                self.stdout.write(f"    - ligne {err['ligne']} : {err['message']}")
            if len(journal.erreurs) > 20:
                self.stdout.write(f"    ... et {len(journal.erreurs) - 20} de plus (voir JournalImport#{journal.pk})")

        self.stdout.write(self.style.WARNING(
            "\nNote : pour importer le registre mensuel officiel du PAD "
            "(classeur multi-onglets 'COLLECTE_DE_DONNEES_NAVIRES_*.xlsx'), "
            "utilisez plutôt : python manage.py import_registre_pad <fichier>"
        ))

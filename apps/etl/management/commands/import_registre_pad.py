from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.etl.registre_pad.service import run_import_registre_pad


class Command(BaseCommand):
    help = (
        "Importe le registre mensuel des escales du PAD (classeur Excel multi-onglets "
        "'COLLECTE_DE_DONNEES_NAVIRES_*.xlsx')."
    )

    def add_arguments(self, parser):
        parser.add_argument("chemin_fichier", type=str)

    def handle(self, *args, **options):
        chemin = Path(options["chemin_fichier"])
        if not chemin.exists():
            raise CommandError(f"Fichier introuvable : {chemin}")

        self.stdout.write(f"Import du registre {chemin.name}...")
        resultat = run_import_registre_pad(str(chemin), source_name=chemin.name)

        journal = resultat.journal
        self.stdout.write(self.style.SUCCESS(f"Journal d'import #{journal.pk} — statut : {journal.statut}"))
        self.stdout.write(f"  Lignes lues     : {journal.nb_lignes_lues}")
        self.stdout.write(f"  Lignes chargées : {journal.nb_lignes_chargees}")
        self.stdout.write(f"  Lignes rejetées : {journal.nb_lignes_rejetees}")
        if resultat.rapport_qualite:
            self.stdout.write(f"  {resultat.rapport_qualite.summary()}")

        if journal.erreurs:
            self.stdout.write(self.style.WARNING(f"Anomalies détectées ({len(journal.erreurs)}) :"))
            for err in journal.erreurs[:30]:
                self.stdout.write(f"    - ligne {err['ligne']} : {err['message']}")
            if len(journal.erreurs) > 30:
                self.stdout.write(f"    ... et {len(journal.erreurs) - 30} de plus (voir JournalImport#{journal.pk})")

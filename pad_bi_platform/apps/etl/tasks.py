"""
Tâches Celery pour l'exécution asynchrone du pipeline ETL et le déclenchement
du recalcul des KPI après un import réussi (planification via Celery beat).
"""
from celery import shared_task


@shared_task(bind=True, max_retries=2)
def importer_fichier_async(self, chemin_fichier: str, source_name: str, format: str, utilisateur_id=None):
    """Exécute run_import() en arrière-plan (utilisé par l'API pour les gros fichiers)."""
    from django.contrib.auth import get_user_model

    from .services import run_import

    utilisateur = None
    if utilisateur_id:
        utilisateur = get_user_model().objects.filter(pk=utilisateur_id).first()

    resultat = run_import(chemin_fichier, source_name=source_name, format=format, utilisateur=utilisateur)

    if resultat.reussi:
        recalculer_kpi_apres_import.delay(resultat.journal.pk)

    return resultat.journal.pk


@shared_task
def recalculer_kpi_apres_import(journal_import_id: int):
    """
    Déclenche le recalcul des KPI impactés par un import (Module 3).
    Implémentation détaillée dans l'app `kpi` (prochaine étape du projet).
    """
    from apps.etl.models import JournalImport

    journal = JournalImport.objects.get(pk=journal_import_id)
    # TODO: apps.kpi.engine.calculators.recalculer(periode=...)
    return f"Recalcul des KPI déclenché suite à l'import #{journal.pk}"

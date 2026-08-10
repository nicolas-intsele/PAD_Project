"""
Orchestrateur du pipeline ETL complet :
extraction -> contrôle qualité -> nettoyage -> chargement -> historisation.

C'est le point d'entrée unique utilisé aussi bien par la commande CLI
(management command), l'API REST (views.py) que les tâches planifiées
(tasks.py Celery).
"""
from __future__ import annotations

import logging

from .importers.csv_importer import CSVImporter
from .importers.excel_importer import ExcelImporter
from .loader import EscaleLoader
from .models import JournalImport
from .transformers import nettoyer_dataframe
from .validators import DataQualityController

logger = logging.getLogger(__name__)

IMPORTERS = {
    "csv": CSVImporter,
    "excel": ExcelImporter,
    "xlsx": ExcelImporter,
}


class ImportResult:
    def __init__(self, journal: JournalImport, rapport_qualite):
        self.journal = journal
        self.rapport_qualite = rapport_qualite

    @property
    def reussi(self) -> bool:
        return self.journal.statut in (JournalImport.Statut.SUCCES, JournalImport.Statut.PARTIEL)


def run_import(source, source_name: str, format: str = "csv", utilisateur=None) -> ImportResult:
    """
    Exécute la totalité du pipeline ETL pour un fichier donné.

    :param source: chemin de fichier ou objet fichier (UploadedFile Django, etc.)
    :param source_name: nom d'affichage de la source (utilisé pour l'historisation)
    :param format: 'csv' ou 'excel'
    :param utilisateur: utilisateur Django à l'origine de l'import (facultatif)
    """
    journal = JournalImport.objects.create(source=source_name, utilisateur=utilisateur)
    logger.info("Import #%s démarré : %s (%s)", journal.pk, source_name, format)

    try:
        importer_cls = IMPORTERS.get(format)
        if importer_cls is None:
            raise ValueError(f"Format d'import non supporté : {format}")

        # 1. EXTRACTION
        df_brut = importer_cls().extract(source)
        journal.nb_lignes_lues = len(df_brut)

        # 2. CONTRÔLE QUALITÉ
        rapport = DataQualityController(df_brut).controler()
        for issue in rapport.to_list():
            journal.ajouter_erreur(issue["ligne"], issue["message"], bloquant=issue["bloquant"])

        if not rapport.is_valid and len(rapport.blocking_lines) >= len(df_brut):
            # Aucune ligne exploitable : on arrête le pipeline ici
            journal.marquer_echec()
            logger.warning("Import #%s rejeté : %s", journal.pk, rapport.summary())
            return ImportResult(journal, rapport)

        # 3. TRANSFORMATION
        df_propre = nettoyer_dataframe(df_brut)

        # 4. CHARGEMENT (les lignes bloquantes du contrôle qualité sont ignorées)
        loader = EscaleLoader(journal_import=journal)
        nb_chargees, erreurs_chargement = loader.charger(df_propre, lignes_ignorees=rapport.blocking_lines)
        for err in erreurs_chargement:
            journal.ajouter_erreur(err["ligne"], err["message"], bloquant=True)

        # 5. HISTORISATION
        journal.marquer_succes(nb_chargees)
        logger.info(
            "Import #%s terminé : %s/%s lignes chargées (%s)",
            journal.pk, nb_chargees, journal.nb_lignes_lues, rapport.summary(),
        )
        return ImportResult(journal, rapport)

    except Exception:
        logger.exception("Import #%s : échec inattendu", journal.pk)
        journal.marquer_echec()
        raise

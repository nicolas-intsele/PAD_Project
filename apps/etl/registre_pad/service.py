"""Orchestrateur du pipeline ETL pour le registre mensuel réel du PAD."""
from __future__ import annotations

import logging

from apps.etl.models import JournalImport
from apps.etl.services import ImportResult

from .extractor import extraire_escales, extraire_navires_reference, extraire_quais_reference
from .loader import ReferentielCache, RegistrePADLoader
from .validators import RegistrePADQualityController

logger = logging.getLogger(__name__)


def run_import_registre_pad(fichier, source_name: str, utilisateur=None) -> ImportResult:
    """
    Pipeline ETL dédié au format réel "Registre mensuel des escales" du PAD
    (classeur multi-onglets avec référentiels navires et quais intégrés).
    """
    journal = JournalImport.objects.create(source=source_name, utilisateur=utilisateur)
    logger.info("Import registre PAD #%s démarré : %s", journal.pk, source_name)

    try:
        # 1. EXTRACTION (escales de tous les onglets mensuels non vides + référentiels)
        df_escales = extraire_escales(fichier)
        df_navires_ref = extraire_navires_reference(fichier)
        df_quais_ref = extraire_quais_reference(fichier)
        journal.nb_lignes_lues = len(df_escales)

        if df_escales.empty:
            journal.ajouter_erreur(0, "Aucune donnée d'escale trouvée dans le classeur (tous les onglets mensuels sont vides)")
            journal.marquer_echec()
            return ImportResult(journal, None)

        # 2. CONTRÔLE QUALITÉ
        rapport = RegistrePADQualityController(df_escales).controler()
        for issue in rapport.to_list():
            journal.ajouter_erreur(issue["ligne"], issue["message"])

        # 3. CHARGEMENT (résolution navires/quais via référentiels + table de faits)
        cache = ReferentielCache(df_navires_ref, df_quais_ref)
        loader = RegistrePADLoader(cache, journal_import=journal)
        nb_chargees, erreurs_chargement = loader.charger(df_escales, lignes_ignorees=rapport.blocking_lines)
        for err in erreurs_chargement:
            journal.ajouter_erreur(err["ligne"], err["message"])

        # 4. HISTORISATION
        journal.marquer_succes(nb_chargees)
        logger.info(
            "Import registre PAD #%s terminé : %s/%s lignes chargées (%s)",
            journal.pk, nb_chargees, journal.nb_lignes_lues, rapport.summary(),
        )
        return ImportResult(journal, rapport)

    except Exception:
        logger.exception("Import registre PAD #%s : échec inattendu", journal.pk)
        journal.marquer_echec()
        raise

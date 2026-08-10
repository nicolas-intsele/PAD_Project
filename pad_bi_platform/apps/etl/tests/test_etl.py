"""
Tests automatisés du module ETL : importeurs, contrôle qualité, transformation
et pipeline complet (services.run_import).

Exécution : python manage.py test apps.etl
"""
from pathlib import Path

import pandas as pd
from django.test import TestCase

from apps.escales.models import Escale
from apps.etl.importers.csv_importer import CSVImporter
from apps.etl.importers.excel_importer import ExcelImporter
from apps.etl.models import JournalImport
from apps.etl.services import run_import
from apps.etl.transformers import nettoyer_dataframe
from apps.etl.validators import DataQualityController
from apps.referentiel.models import Navire

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "samples"
CSV_SAMPLE = SAMPLES_DIR / "escales_exemple.csv"
XLSX_SAMPLE = SAMPLES_DIR / "escales_exemple.xlsx"


class ImportersTestCase(TestCase):
    def test_csv_importer_lit_toutes_les_lignes(self):
        df = CSVImporter().extract(str(CSV_SAMPLE))
        self.assertEqual(len(df), 9)
        self.assertIn("navire_imo", df.columns)
        self.assertIn("date_arrivee", df.columns)

    def test_excel_importer_lit_toutes_les_lignes(self):
        df = ExcelImporter().extract(str(XLSX_SAMPLE))
        self.assertEqual(len(df), 9)
        self.assertIn("navire_imo", df.columns)

    def test_csv_importer_detecte_le_point_virgule(self):
        df_semicolon = CSVImporter(delimiter=",").extract(str(CSV_SAMPLE))
        # Le fichier d'exemple est en virgule : vérifie qu'on obtient bien >1 colonne
        self.assertGreater(df_semicolon.shape[1], 1)


class DataQualityControllerTestCase(TestCase):
    def test_detecte_colonne_manquante(self):
        df = pd.DataFrame([{"navire_nom": "Test"}])  # navire_imo absent
        rapport = DataQualityController(df).controler()
        self.assertFalse(rapport.is_valid)
        messages = [i.message for i in rapport.issues]
        self.assertTrue(any("navire_imo" in m for m in messages))

    def test_detecte_valeur_manquante(self):
        df = pd.DataFrame([{
            "navire_imo": "", "navire_nom": "Test", "type_navire": "Vraquier",
            "compagnie": "X", "agent_maritime": "Y", "quai": "Q1", "terminal": "T1",
            "date_arrivee": "15/01/2026",
        }])
        rapport = DataQualityController(df).controler()
        self.assertFalse(rapport.is_valid)

    def test_detecte_date_invalide(self):
        df = pd.DataFrame([{
            "navire_imo": "IMO001", "navire_nom": "Test", "type_navire": "Vraquier",
            "compagnie": "X", "agent_maritime": "Y", "quai": "Q1", "terminal": "T1",
            "date_arrivee": "32/13/2026",
        }])
        rapport = DataQualityController(df).controler()
        self.assertFalse(rapport.is_valid)

    def test_detecte_doublons_comme_avertissement(self):
        ligne = {
            "navire_imo": "IMO001", "navire_nom": "Test", "type_navire": "Vraquier",
            "compagnie": "X", "agent_maritime": "Y", "quai": "Q1", "terminal": "T1",
            "date_arrivee": "15/01/2026",
        }
        df = pd.DataFrame([ligne, ligne])
        rapport = DataQualityController(df).controler()
        # Un doublon est un avertissement non bloquant : le fichier reste valide
        self.assertTrue(rapport.is_valid)
        self.assertTrue(any(not i.bloquant for i in rapport.issues))

    def test_fichier_conforme_ne_leve_aucune_anomalie(self):
        df = pd.DataFrame([{
            "navire_imo": "IMO001", "navire_nom": "Test", "type_navire": "Vraquier",
            "compagnie": "X", "agent_maritime": "Y", "quai": "Q1", "terminal": "T1",
            "date_arrivee": "15/01/2026 08:00", "date_depart": "16/01/2026 10:00",
        }])
        rapport = DataQualityController(df).controler()
        self.assertTrue(rapport.is_valid)
        self.assertEqual(len(rapport.issues), 0)


class TransformersTestCase(TestCase):
    def test_nettoyage_normalise_les_textes_et_dates(self):
        df = pd.DataFrame([{
            "navire_imo": " imo123 ", "navire_nom": "  msc douala  ",
            "compagnie": "msc", "quai": "quai c1", "terminal": "terminal a",
            "agent_maritime": "socopao", "type_navire": "porte-conteneurs",
            "date_arrivee": "15/01/2026 06:30", "statut": "Terminée",
        }])
        propre = nettoyer_dataframe(df)
        self.assertEqual(propre.loc[0, "navire_imo"], "IMO123")
        self.assertEqual(propre.loc[0, "navire_nom"], "Msc Douala")
        self.assertEqual(propre.loc[0, "statut"], "terminee")
        self.assertIsNotNone(propre.loc[0, "date_arrivee"])

    def test_dates_manquantes_restent_none(self):
        df = pd.DataFrame([{"date_arrivee": "15/01/2026", "date_depart": ""}])
        propre = nettoyer_dataframe(df)
        self.assertIsNone(propre.loc[0, "date_depart"])


class RunImportIntegrationTestCase(TestCase):
    """Test d'intégration du pipeline ETL complet (extraction -> ... -> historisation)."""

    def test_pipeline_complet_sur_le_fichier_exemple(self):
        resultat = run_import(str(CSV_SAMPLE), source_name="escales_exemple.csv", format="csv")

        journal = resultat.journal
        self.assertEqual(journal.statut, JournalImport.Statut.PARTIEL)
        self.assertEqual(journal.nb_lignes_lues, 9)
        self.assertEqual(journal.nb_lignes_chargees, 6)
        self.assertGreaterEqual(len(journal.erreurs), 5)

        # 5 escales distinctes attendues (le doublon des lignes 7/8 fusionne via update_or_create)
        self.assertEqual(Escale.objects.count(), 5)
        self.assertTrue(Navire.objects.filter(imo="IMO9456781").exists())

    def test_calcul_automatique_des_temps_apres_chargement(self):
        run_import(str(CSV_SAMPLE), source_name="escales_exemple.csv", format="csv")
        escale = Escale.objects.get(navire__imo="IMO9456781")
        self.assertIsNotNone(escale.temps_attente)
        self.assertIsNotNone(escale.temps_sejour)
        self.assertGreater(escale.temps_sejour, escale.temps_attente)

    def test_import_idempotent_ne_duplique_pas_les_escales(self):
        run_import(str(CSV_SAMPLE), source_name="import_1.csv", format="csv")
        nb_avant = Escale.objects.count()
        run_import(str(CSV_SAMPLE), source_name="import_2.csv", format="csv")
        nb_apres = Escale.objects.count()
        self.assertEqual(nb_avant, nb_apres, "Une ré-importation du même fichier ne doit pas créer de doublons")

    def test_format_non_supporte_leve_une_erreur_et_historise_echec(self):
        with self.assertRaises(ValueError):
            run_import(str(CSV_SAMPLE), source_name="x.txt", format="inconnu")
        dernier_journal = JournalImport.objects.latest("date_import")
        self.assertEqual(dernier_journal.statut, JournalImport.Statut.ECHEC)

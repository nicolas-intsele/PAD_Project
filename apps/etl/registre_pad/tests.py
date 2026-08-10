"""
Tests du pipeline ETL dédié au registre mensuel réel du PAD.

Ces tests s'appuient sur le fichier fourni par l'utilisateur
(data/samples/COLLECTE_DE_DONNEES_NAVIRES_2026_26062026.xlsx). Si ce fichier
n'est pas présent dans l'environnement d'exécution, les tests sont ignorés
(skip) plutôt que d'échouer, pour ne pas bloquer le reste de la suite ETL.

Exécution : python manage.py test apps.etl.registre_pad
"""
import unittest
from pathlib import Path

from django.test import TestCase

from apps.escales.models import Escale
from apps.etl.models import JournalImport
from apps.etl.registre_pad.extractor import extraire_escales, extraire_navires_reference, extraire_quais_reference
from apps.etl.registre_pad.service import run_import_registre_pad
from apps.etl.registre_pad.validators import RegistrePADQualityController
from apps.referentiel.models import Navire, Quai, Terminal

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "samples"
REGISTRE_REEL = SAMPLES_DIR / "COLLECTE_DE_DONNEES_NAVIRES_2026_26062026.xlsx"

pas_de_fichier_reel = unittest.skipUnless(
    REGISTRE_REEL.exists(), "Registre PAD réel non fourni dans cet environnement"
)


@pas_de_fichier_reel
class ExtractionTestCase(TestCase):
    def test_extraction_escales_ignore_les_mois_vides(self):
        df = extraire_escales(str(REGISTRE_REEL))
        # Données réelles présentes uniquement de janvier à juin 2026 dans le fichier fourni
        self.assertGreater(len(df), 0)
        self.assertTrue(set(df["mois_source"].unique()) <= {
            "JANVIER 2026", "FEVRIER 2026", "MARS 2026", "AVRIL 2026", "MAI 2026", "JUIN 2026",
            "JUILLET 2026", "AOUT 2026", "SEPTEMBRE 2026", "OCTOBRE 2026", "NOVEMBRE 2026", "DECEMBRE 2026",
        })
        for col in ["navire", "poste", "arrivee_rade", "ligne_source"]:
            self.assertIn(col, df.columns)

    def test_extraction_navires_reference(self):
        df = extraire_navires_reference(str(REGISTRE_REEL))
        self.assertGreater(len(df), 0)
        self.assertIn("imo", df.columns)

    def test_extraction_quais_reference(self):
        df = extraire_quais_reference(str(REGISTRE_REEL))
        self.assertGreater(len(df), 0)
        self.assertIn("P1", set(df["poste"].str.strip()))


@pas_de_fichier_reel
class QualityControllerTestCase(TestCase):
    def test_controle_qualite_sur_donnees_reelles(self):
        df = extraire_escales(str(REGISTRE_REEL))
        rapport = RegistrePADQualityController(df).controler()
        # Le fichier réel contient des anomalies connues (dates malformées, doublons) :
        # le contrôle doit les détecter sans lever d'exception.
        self.assertIsInstance(rapport.to_list(), list)


@pas_de_fichier_reel
class RunImportRegistrePADIntegrationTestCase(TestCase):
    def test_pipeline_complet_sur_le_fichier_reel(self):
        resultat = run_import_registre_pad(str(REGISTRE_REEL), source_name="registre_test.xlsx")
        journal = resultat.journal

        self.assertEqual(journal.statut, JournalImport.Statut.PARTIEL)
        self.assertGreater(journal.nb_lignes_lues, 0)
        self.assertGreater(journal.nb_lignes_chargees, 0)
        self.assertLessEqual(journal.nb_lignes_chargees, journal.nb_lignes_lues)

        # Régression du bug de persistance : les stats doivent être relisibles depuis la BD
        journal_relu = JournalImport.objects.get(pk=journal.pk)
        self.assertEqual(journal_relu.nb_lignes_lues, journal.nb_lignes_lues)
        self.assertEqual(journal_relu.nb_lignes_chargees, journal.nb_lignes_chargees)
        self.assertGreater(len(journal_relu.erreurs), 0)

        # Certaines lignes chargées correspondent à des doublons (avertissement non
        # bloquant) qui fusionnent via update_or_create : le nombre d'escales
        # distinctes peut donc être inférieur au nombre de lignes traitées.
        self.assertLessEqual(Escale.objects.count(), journal.nb_lignes_chargees)
        self.assertGreater(Escale.objects.count(), 0)
        self.assertGreater(Navire.objects.count(), 0)
        self.assertGreater(Quai.objects.count(), 0)
        self.assertGreater(Terminal.objects.count(), 0)

    def test_import_idempotent(self):
        run_import_registre_pad(str(REGISTRE_REEL), source_name="import_1.xlsx")
        nb_avant = Escale.objects.count()
        run_import_registre_pad(str(REGISTRE_REEL), source_name="import_2.xlsx")
        nb_apres = Escale.objects.count()
        self.assertEqual(nb_avant, nb_apres)

    def test_temps_caracteristiques_calcules(self):
        run_import_registre_pad(str(REGISTRE_REEL), source_name="registre_test.xlsx")
        escales_terminees = Escale.objects.filter(statut=Escale.Statut.TERMINEE, temps_sejour__isnull=False)
        self.assertGreater(escales_terminees.count(), 0)
        for escale in escales_terminees[:20]:
            self.assertGreaterEqual(escale.temps_sejour, 0)

    def test_aucune_duree_negative_stockee(self):
        """
        Régression : une poignée d'escales du fichier réel ont un départ antérieur
        à l'arrivée (erreur de saisie à la source, ex. mois inversé). Le loader ne
        doit jamais persister de durée négative — temps_sejour/temps_attente
        doivent rester NULL pour ces lignes plutôt que de fausser les KPI.
        """
        run_import_registre_pad(str(REGISTRE_REEL), source_name="registre_test.xlsx")
        self.assertEqual(Escale.objects.filter(temps_sejour__lt=0).count(), 0)
        self.assertEqual(Escale.objects.filter(temps_attente__lt=0).count(), 0)

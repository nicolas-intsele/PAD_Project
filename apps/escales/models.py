"""
Table de faits ESCALE et table de jonction MOBILISER.
Correspond à l'association porteuse ESCALE du MCD (voir docs/MCD_MLD_MPD_PAD.docx).

Alignée explicitement sur docs/schema_pad.sql (Meta.db_table + db_column)
pour écrire directement dans les tables "escale" / "mobiliser" existantes.
"""
from django.db import models

from apps.referentiel.models import AgentMaritime, Calendrier, Navire, Poste, ServiceNautique


class Escale(models.Model):
    class Statut(models.TextChoices):
        PLANIFIEE = "planifiee", "Planifiée"
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ANNULEE = "annulee", "Annulée"

    id_escale = models.AutoField(primary_key=True)
    navire = models.ForeignKey(Navire, on_delete=models.PROTECT, related_name="escales", db_column="id_navire")
    poste = models.ForeignKey(Poste, on_delete=models.PROTECT, related_name="escales", db_column="id_poste")
    agent = models.ForeignKey(AgentMaritime, on_delete=models.PROTECT, related_name="escales", db_column="id_agent")
    date_ref = models.ForeignKey(Calendrier, on_delete=models.PROTECT, related_name="escales", db_column="id_date")

    date_arrivee = models.DateTimeField()
    date_accostage = models.DateTimeField(null=True, blank=True)
    date_appareillage = models.DateTimeField(null=True, blank=True)
    date_depart = models.DateTimeField(null=True, blank=True)

    temps_attente = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="en heures")
    temps_sejour = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    temps_pilotage = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    temps_accostage = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    # Tonnages manutentionnés (alimente le KPI de productivité — Module 3).
    # Colonnes absentes de docs/schema_pad.sql (ajoutées après coup, comme
    # import_source) : voir docs/ALTER_schema_django.sql.
    tonnage_debarque = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tonnage_embarque = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PLANIFIEE)

    # Mois de référence de l'onglet source (AAAA-MM).
    # Un navire arrivé en décembre mais enregistré dans l'onglet janvier
    # aura mois_source="2026-01". C'est ce champ qui sert au calcul des KPI
    # (Option B : on compte les escales par onglet mensuel, pas par date d'arrivée).
    mois_source = models.CharField(max_length=7, blank=True, null=True,
                                   help_text="Mois de l'onglet source, format AAAA-MM")

    # Traçabilité de la source d'import. Colonne absente de docs/schema_pad.sql
    # (ajoutée après coup pour l'ETL) : voir docs/ALTER_schema_django.sql pour
    # l'instruction ALTER TABLE à exécuter une seule fois sur une base créée
    # directement à partir de schema_pad.sql.
    import_source = models.ForeignKey(
        "etl.JournalImport", on_delete=models.SET_NULL, null=True, blank=True, related_name="escales"
    )

    class Meta:
        db_table = "escale"
        verbose_name = "Escale"
        indexes = [
            models.Index(fields=["navire"]),
            models.Index(fields=["poste"]),
            models.Index(fields=["date_ref"]),
            # MO5 (audit Phase 7) : colonnes filtrées dans tous les calculs KPI et scans alertes.
            # Sans ces index, chaque appel à calculer_kpi_mois() et scanner_escales_critiques()
            # scanne la table entière — invisible à 300 lignes, critique à l'échelle réelle du PAD.
            models.Index(fields=["date_arrivee"]),
            models.Index(fields=["date_accostage"]),
            models.Index(fields=["date_depart"]),
        ]

    def __str__(self):
        return f"Escale {self.navire} @ {self.poste} ({self.date_arrivee:%Y-%m-%d})"

    def calculer_temps_attente(self):
        """
        Temps d'attente = pilote_a_bord_arrivee - arrivee_rade (en heures).
        Correspond au temps que le navire attend en rade avant que le pilote
        monte à bord pour le conduire à son poste d'accostage.
        """
        if self.date_arrivee and self.date_accostage:
            # date_arrivee = arrivee_rade, date_accostage = pilote_a_bord_arrivee
            delta = self.date_accostage - self.date_arrivee
            heures = delta.total_seconds() / 3600
            return round(heures, 2) if heures >= 0 else None
        return None

    def calculer_duree_sejour(self):
        """
        Temps de séjour = navire_appareille - arrivee_poste (en heures).
        Durée réelle passée à quai (du moment où le navire est à poste
        jusqu'à son appareillage).
        """
        if self.date_appareillage and self.date_depart:
            # date_depart = arrivee_poste, date_appareillage = navire_appareille
            delta = self.date_appareillage - self.date_depart
            heures = delta.total_seconds() / 3600
            return round(heures, 2) if heures >= 0 else None
        return None

    def est_en_retard(self, seuil_heures=48):
        duree = self.calculer_duree_sejour()
        return duree is not None and duree > seuil_heures


class Mobiliser(models.Model):
    """
    Table de jonction n,n entre ESCALE et SERVICE_NAUTIQUE.

    Non encore alimentée par le pipeline ETL actuel (le journal des
    mouvements/services mobilisés sera traité avec le module Alertes/KPI).
    NOTE : docs/schema_pad.sql définit une clé primaire composite
    (id_escale, id_service) sans colonne id séparée ; ce modèle conserve un
    id technique Django pour rester compatible avec l'ORM standard — voir
    docs/ALTER_schema_django.sql si vous souhaitez l'aligner strictement.
    """

    escale = models.ForeignKey(Escale, on_delete=models.CASCADE, related_name="services_mobilises", db_column="id_escale")
    service = models.ForeignKey(ServiceNautique, on_delete=models.PROTECT, related_name="mobilisations", db_column="id_service")
    duree_reelle = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    ordre_intervention = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "mobiliser"
        verbose_name = "Mobilisation de service nautique"
        verbose_name_plural = "Mobilisations de services nautiques"
        constraints = [
            models.UniqueConstraint(fields=["escale", "service"], name="uq_mobiliser_escale_service")
        ]

    def __str__(self):
        return f"{self.service} pour {self.escale}"
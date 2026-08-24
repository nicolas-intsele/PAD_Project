"""
Table de faits ESCALE et table de jonction MOBILISER.
Correspond à l'association porteuse ESCALE du MCD (voir docs/MCD_MLD_MPD_PAD.docx).

Alignée explicitement sur docs/schema_pad.sql (Meta.db_table + db_column)
pour écrire directement dans les tables "escale" / "mobiliser" existantes.
"""
from django.db import models

from apps.referentiel.models import AgentMaritime, Calendrier, Navire, Quai, ServiceNautique


class Escale(models.Model):
    class Statut(models.TextChoices):
        PLANIFIEE = "planifiee", "Planifiée"
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ANNULEE = "annulee", "Annulée"

    id_escale = models.AutoField(primary_key=True)
    navire = models.ForeignKey(Navire, on_delete=models.PROTECT, related_name="escales", db_column="id_navire")
    quai = models.ForeignKey(Quai, on_delete=models.PROTECT, related_name="escales", db_column="id_quai")
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
            models.Index(fields=["quai"]),
            models.Index(fields=["date_ref"]),
        ]

    def __str__(self):
        return f"Escale {self.navire} @ {self.quai} ({self.date_arrivee:%Y-%m-%d})"

    def calculer_temps_attente(self):
        """Temps écoulé entre l'arrivée et l'accostage effectif (en heures).
        Retourne None si les dates sont incohérentes (accostage avant arrivée),
        plutôt que de stocker une durée négative qui fausserait les KPI."""
        if self.date_arrivee and self.date_accostage:
            delta = self.date_accostage - self.date_arrivee
            heures = delta.total_seconds() / 3600
            return round(heures, 2) if heures >= 0 else None
        return None

    def calculer_duree_sejour(self):
        """Durée totale entre l'arrivée et le départ du navire (en heures).
        Retourne None si les dates sont incohérentes (départ avant arrivée)."""
        if self.date_arrivee and self.date_depart:
            delta = self.date_depart - self.date_arrivee
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
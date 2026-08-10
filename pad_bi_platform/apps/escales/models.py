"""
Table de faits ESCALE et table de jonction MOBILISER.
Correspond à l'association porteuse ESCALE du MCD (voir docs/MCD_MLD_MPD_PAD.docx).
"""
from django.db import models

from apps.referentiel.models import AgentMaritime, Calendrier, Navire, Quai, ServiceNautique


class Escale(models.Model):
    class Statut(models.TextChoices):
        PLANIFIEE = "planifiee", "Planifiée"
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ANNULEE = "annulee", "Annulée"

    navire = models.ForeignKey(Navire, on_delete=models.PROTECT, related_name="escales")
    quai = models.ForeignKey(Quai, on_delete=models.PROTECT, related_name="escales")
    agent = models.ForeignKey(AgentMaritime, on_delete=models.PROTECT, related_name="escales")
    date_ref = models.ForeignKey(Calendrier, on_delete=models.PROTECT, related_name="escales")

    date_arrivee = models.DateTimeField()
    date_accostage = models.DateTimeField(null=True, blank=True)
    date_appareillage = models.DateTimeField(null=True, blank=True)
    date_depart = models.DateTimeField(null=True, blank=True)

    temps_attente = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="en heures")
    temps_sejour = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    temps_pilotage = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    temps_accostage = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PLANIFIEE)

    # Traçabilité de la source d'import (utile pour l'historisation ETL)
    import_source = models.ForeignKey(
        "etl.JournalImport", on_delete=models.SET_NULL, null=True, blank=True, related_name="escales"
    )

    class Meta:
        verbose_name = "Escale"
        indexes = [
            models.Index(fields=["navire"]),
            models.Index(fields=["quai"]),
            models.Index(fields=["date_ref"]),
        ]

    def __str__(self):
        return f"Escale {self.navire} @ {self.quai} ({self.date_arrivee:%Y-%m-%d})"

    def calculer_temps_attente(self):
        """Temps écoulé entre l'arrivée et l'accostage effectif (en heures)."""
        if self.date_arrivee and self.date_accostage:
            delta = self.date_accostage - self.date_arrivee
            return round(delta.total_seconds() / 3600, 2)
        return None

    def calculer_duree_sejour(self):
        """Durée totale entre l'arrivée et le départ du navire (en heures)."""
        if self.date_arrivee and self.date_depart:
            delta = self.date_depart - self.date_arrivee
            return round(delta.total_seconds() / 3600, 2)
        return None

    def est_en_retard(self, seuil_heures=48):
        duree = self.calculer_duree_sejour()
        return duree is not None and duree > seuil_heures


class Mobiliser(models.Model):
    """Table de jonction n,n entre ESCALE et SERVICE_NAUTIQUE."""

    escale = models.ForeignKey(Escale, on_delete=models.CASCADE, related_name="services_mobilises")
    service = models.ForeignKey(ServiceNautique, on_delete=models.PROTECT, related_name="mobilisations")
    duree_reelle = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    ordre_intervention = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Mobilisation de service nautique"
        verbose_name_plural = "Mobilisations de services nautiques"
        constraints = [
            models.UniqueConstraint(fields=["escale", "service"], name="uq_mobiliser_escale_service")
        ]

    def __str__(self):
        return f"{self.service} pour {self.escale}"

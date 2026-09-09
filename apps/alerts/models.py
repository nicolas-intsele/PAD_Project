"""
Module 6 — Alertes & Aide à la décision.

Modèles :
  - Alerte         : occurrence d'une anomalie détectée (KPI hors seuil ou escale critique)
  - UtilisateurAlerte : liaison utilisateur ↔ alerte (lecture, acquittement)
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.escales.models import Escale
from apps.kpi.models import SeuilAlerte


class Alerte(models.Model):
    class TypeAlerte(models.TextChoices):
        KPI_SEUIL      = "kpi_seuil",      "KPI hors seuil"
        CONGESTION     = "congestion",     "Congestion détectée"
        RETARD         = "retard",         "Retard escale"
        OCCUPATION     = "occupation",     "Taux occupation élevé"
        ATTENTE_LONGUE = "attente_longue", "Temps d'attente excessif"

    class Statut(models.TextChoices):
        ACTIVE     = "active",     "Active"
        ACQUITTEE  = "acquittee",  "Acquittée"
        RESOLUE    = "resolue",    "Résolue"

    seuil   = models.ForeignKey(
        SeuilAlerte, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="alertes", verbose_name="Seuil déclencheur"
    )
    escale  = models.ForeignKey(
        Escale, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="alertes", verbose_name="Escale concernée"
    )
    type_alerte         = models.CharField(max_length=20, choices=TypeAlerte.choices)
    niveau_gravite      = models.CharField(
        max_length=20,
        choices=[("info", "Information"), ("avertissement", "Avertissement"), ("critique", "Critique")],
        default="avertissement",
    )
    message             = models.TextField()
    valeur_declenchante = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    date_declenchement  = models.DateTimeField(default=timezone.now)
    statut              = models.CharField(max_length=15, choices=Statut.choices, default=Statut.ACTIVE)
    date_resolution     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "alerte"
        verbose_name = "Alerte"
        verbose_name_plural = "Alertes"
        ordering = ["-date_declenchement"]
        indexes = [
            models.Index(fields=["statut"]),
            models.Index(fields=["niveau_gravite"]),
            models.Index(fields=["date_declenchement"]),
        ]

    def __str__(self):
        return f"[{self.niveau_gravite.upper()}] {self.type_alerte} — {self.date_declenchement:%d/%m/%Y %H:%M}"

    def acquitter(self, user=None):
        self.statut = self.Statut.ACQUITTEE
        self.save(update_fields=["statut"])
        if user:
            UtilisateurAlerte.objects.get_or_create(
                utilisateur=user, alerte=self,
                defaults={"statut_lecture": "lu"},
            )

    def resoudre(self):
        self.statut = self.Statut.RESOLUE
        self.date_resolution = timezone.now()
        self.save(update_fields=["statut", "date_resolution"])

    @property
    def est_active(self):
        return self.statut == self.Statut.ACTIVE

    @property
    def icone(self):
        return {"info": "bi-info-circle", "avertissement": "bi-exclamation-triangle",
                "critique": "bi-exclamation-octagon"}.get(self.niveau_gravite, "bi-bell")

    @property
    def couleur_css(self):
        return {"info": "primary", "avertissement": "warning",
                "critique": "danger"}.get(self.niveau_gravite, "secondary")


class UtilisateurAlerte(models.Model):
    class StatutLecture(models.TextChoices):
        NON_LU = "non_lu", "Non lu"
        LU     = "lu",     "Lu"

    utilisateur   = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alertes_utilisateur")
    alerte        = models.ForeignKey(Alerte, on_delete=models.CASCADE, related_name="notifications")
    date_lecture  = models.DateTimeField(null=True, blank=True)
    statut_lecture = models.CharField(
        max_length=10, choices=StatutLecture.choices, default=StatutLecture.NON_LU
    )

    class Meta:
        db_table = "utilisateur_alerte"
        verbose_name = "Notification d'alerte"
        unique_together = [("utilisateur", "alerte")]

    def marquer_lu(self):
        self.statut_lecture = self.StatutLecture.LU
        self.date_lecture   = timezone.now()
        self.save(update_fields=["statut_lecture", "date_lecture"])

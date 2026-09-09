"""
Module 7 — Reporting.

Modèles :
  - Rapport    : métadonnées d'un rapport généré (type, période, format, fichier)
  - RapportKPI : association Rapport ↔ KPI (KPI inclus dans le rapport)
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models


class Rapport(models.Model):
    class TypeRapport(models.TextChoices):
        JOURNALIER  = "journalier",  "Rapport journalier"
        HEBDOMADAIRE = "hebdomadaire", "Rapport hebdomadaire"
        MENSUEL     = "mensuel",     "Rapport mensuel"
        PERSONNALISE = "personnalise", "Rapport personnalisé"

    class Format(models.TextChoices):
        PDF   = "pdf",   "PDF"
        EXCEL = "excel", "Excel (.xlsx)"

    utilisateur    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rapports"
    )
    type_rapport   = models.CharField(max_length=20, choices=TypeRapport.choices)
    periode_debut  = models.DateField()
    periode_fin    = models.DateField()
    format         = models.CharField(max_length=10, choices=Format.choices, default=Format.PDF)
    date_generation = models.DateTimeField(auto_now_add=True)
    fichier        = models.FileField(upload_to="reports/", null=True, blank=True)
    titre          = models.CharField(max_length=200, blank=True)
    nb_pages       = models.PositiveSmallIntegerField(null=True, blank=True)
    taille_octets  = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "rapport"
        verbose_name = "Rapport"
        verbose_name_plural = "Rapports"
        ordering = ["-date_generation"]

    def __str__(self):
        return f"{self.get_type_rapport_display()} — {self.periode_debut} → {self.periode_fin} ({self.format})"

    @property
    def taille_lisible(self):
        if not self.taille_octets:
            return "—"
        kb = self.taille_octets / 1024
        if kb > 1024:
            return f"{kb/1024:.1f} Mo"
        return f"{kb:.0f} Ko"


class RapportKPI(models.Model):
    rapport = models.ForeignKey(Rapport, on_delete=models.CASCADE, related_name="kpis_inclus")
    kpi     = models.ForeignKey("kpi.KPI", on_delete=models.CASCADE, related_name="rapports")

    class Meta:
        db_table = "rapport_kpi"
        verbose_name = "KPI du rapport"
        unique_together = [("rapport", "kpi")]

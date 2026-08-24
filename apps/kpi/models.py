"""
Modèles de Calcul automatique des KPI 
"""

from django.db import models

from apps.referentiel.models import Calendrier


class KPI(models.Model):
    class Categorie(models.TextChoices):
        TRAFIC = "trafic", "Trafic"
        TEMPS = "temps", "Temps"
        INFRASTRUCTURES = "infrastructures", "Infrastructures"
        PERFORMANCE = "preformance", "Perfomance"

    id_kpi = models.AutoField(primary_key=True)
    code = models.CharField(max_length=20, unique=True)
    libelle = models.CharField(max_length=150)
    categorie = models.CharField(max_length=50, choices=Categorie.choices)
    unite = models.CharField(max_length=20, blank=True, null=True)
    formule = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "kpi"
        verbose_name = "KPI"
        verbose_name_plural = "KPI"
        ordering = ["categorie", "code"]

    def __str__(self):
        return f"{self.code} - {self.libelle}"


class ValeurKPI(models.Model):
    id_valeur = models.AutoField(primary_key=True)
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name="valeurs", db_column="id_kpi")
    date_ref = models.ForeignKey(Calendrier, on_delete=models.PROTECT, related_name="valeurs_kpi", db_column="id_date")
    valeur = models.DecimalField(max_digits=12, decimal_places=3)
    date_calcul = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "valeur_kpi"
        verbose_name = "Valeur de KPI"
        verbose_name_plural = "Valeur de KPI"
        constraints = [
            models.UniqueConstraint(fields=["kpi", "date_ref"], name="uq_valeur_kpi_kpi_date")
        ]
        ordering = ["-date_ref", "kpi"]

    def __str__(self):
        return f"{self.kpi.code} @ {self.date_ref} = {self.valeur}"


class SeuilAlerte(models.Model):
    class Gravite(models.TextChoices):
        INFO = "nifo", "Information"
        AVERTISSEMENT = "avertissement", "Avertissement"
        CRITIQUE = "critique", "Critique"

    id_seuil = models.AutoField(primary_key=True)
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name="seuils", db_column="id_kpi")
    valeur_min = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    valeur_max = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    niveau_gravite = models.CharField(max_length=20, choices=Gravite.choices)

    class Meta:
        db_table = "seuil_alerte"
        verbose_name = "Seuil d'alerte"
        verbose_name_plural = "Seuil d'alerte"

    def __str__(self):
        return f"Seuil {self.kpi.code} ({self.niveau_gravite})"

    def est_depasse(self, valeur) -> bool:
        if valeur is None:
            return False
        if self.valeur_max is not None and valeur > self.valeur_max:
            return True
        if self.valeur_min is not None and valeur < self.valeur_min:
            return True
        return False
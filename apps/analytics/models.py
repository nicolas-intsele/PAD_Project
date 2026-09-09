"""
Modèles du module d'analyse multidimensionnelle (Module 4).

Architecture OLAP en étoile :
  - CubeAnalyse   : définit un type d'analyse (ex. "Trafic par terminal")
  - AxeAnalyse    : une dimension de découpage (temps, navire, terminal, compagnie, poste, type_navire)
  - ResultatCube  : cache persistant des résultats agrégés pour éviter le recalcul à chaque requête
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class AxeAnalyse(models.Model):
    """
    Dimension d'analyse disponible pour les requêtes OLAP.
    Chaque axe correspond à une colonne de regroupement dans la table de faits ESCALE
    ou dans l'une de ses dimensions.
    """

    class Type(models.TextChoices):
        TEMPS_MOIS = "temps_mois", "Mois"
        TEMPS_TRIMESTRE = "temps_trimestre", "Trimestre"
        TEMPS_ANNEE = "temps_annee", "Année"
        TERMINAL = "terminal", "Terminal"
        POSTE = "poste", "Poste"
        TYPE_NAVIRE = "type_navire", "Type de navire"
        COMPAGNIE = "compagnie", "Compagnie maritime"
        AGENT = "agent", "Agent maritime"
        STATUT = "statut", "Statut de l'escale"

    code = models.CharField(max_length=30, choices=Type.choices, unique=True)
    libelle = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Axe d'analyse"
        verbose_name_plural = "Axes d'analyse"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.libelle


class CubeAnalyse(models.Model):
    """
    Définition d'un cube OLAP : mesure agrégée × couple d'axes (ligne × colonne).

    Exemples :
      - Nombre d'escales  ×  Terminal  ×  Mois
      - Temps moyen séjour  ×  Type navire  ×  Trimestre
    """

    class Mesure(models.TextChoices):
        NB_ESCALES = "nb_escales", "Nombre d'escales"
        NB_ARRIVEES = "nb_arrivees", "Nombre d'arrivées"
        NB_DEPARTS = "nb_departs", "Nombre de départs"
        TEMPS_ATTENTE_MOY = "temps_attente_moy", "Temps d'attente moyen (h)"
        TEMPS_SEJOUR_MOY = "temps_sejour_moy", "Temps de séjour moyen (h)"
        TEMPS_PILOTAGE_MOY = "temps_pilotage_moy", "Temps de pilotage moyen (h)"
        TAUX_OCCUPATION = "taux_occupation", "Taux d'occupation des postes (%)"
        TONNAGE_TOTAL = "tonnage_total", "Tonnage total manutentionné (t)"
        PRODUCTIVITE = "productivite", "Productivité (t/escale)"
        TAUX_PONCTUALITE = "taux_ponctualite", "Taux de ponctualité (%)"
        TAUX_CONGESTION = "taux_congestion", "Taux de congestion (%)"

    nom = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    mesure = models.CharField(max_length=30, choices=Mesure.choices)
    axe_ligne = models.ForeignKey(
        AxeAnalyse,
        on_delete=models.PROTECT,
        related_name="cubes_ligne",
        help_text="Dimension portée par les lignes du tableau croisé",
    )
    axe_colonne = models.ForeignKey(
        AxeAnalyse,
        on_delete=models.PROTECT,
        related_name="cubes_colonne",
        null=True,
        blank=True,
        help_text="Dimension portée par les colonnes (optionnel — analyse 1D si absent)",
    )
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cube d'analyse"
        verbose_name_plural = "Cubes d'analyse"
        ordering = ["mesure", "nom"]

    def __str__(self) -> str:
        return self.nom


class ResultatCube(models.Model):
    """
    Cache des résultats d'un cube pour une période donnée.
    Stocke le résultat sérialisé en JSON pour éviter le recalcul à chaque consultation.
    """

    cube = models.ForeignKey(CubeAnalyse, on_delete=models.CASCADE, related_name="resultats")
    annee = models.PositiveSmallIntegerField()
    mois_debut = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1-12, null = année entière")
    mois_fin = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1-12, null = année entière")
    donnees = models.JSONField(help_text="Résultat sérialisé du cube (liste de dicts)")
    nb_lignes = models.PositiveIntegerField(default=0)
    date_calcul = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Résultat de cube"
        verbose_name_plural = "Résultats de cube"
        ordering = ["-date_calcul"]
        indexes = [
            models.Index(fields=["cube", "annee", "mois_debut", "mois_fin"]),
        ]

    def __str__(self) -> str:
        periode = f"{self.annee}"
        if self.mois_debut:
            periode += f"-{self.mois_debut:02d}"
            if self.mois_fin and self.mois_fin != self.mois_debut:
                periode += f" → {self.annee}-{self.mois_fin:02d}"
        return f"{self.cube} [{periode}]"

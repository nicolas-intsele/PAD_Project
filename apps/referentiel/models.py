"""
Modèles des dimensions du modèle décisionnel (référentiel).
Traduction directe du Modèle Physique de Données (MPD) — voir docs/MCD_MLD_MPD_PAD.docx
"""
from django.db import models


class TypeNavire(models.Model):
    libelle = models.CharField(max_length=50)
    categorie = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "Type de navire"
        verbose_name_plural = "Types de navire"

    def __str__(self):
        return self.libelle


class CompagnieMaritime(models.Model):
    raison_sociale = models.CharField(max_length=150)
    pays = models.CharField(max_length=80, blank=True)

    class Meta:
        verbose_name = "Compagnie maritime"
        verbose_name_plural = "Compagnies maritimes"

    def __str__(self):
        return self.raison_sociale


class Terminal(models.Model):
    nom = models.CharField(max_length=100)
    specialite = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Terminal"

    def __str__(self):
        return self.nom


class AgentMaritime(models.Model):
    nom = models.CharField(max_length=150)
    contact = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Agent maritime"
        verbose_name_plural = "Agents maritimes"

    def __str__(self):
        return self.nom


class ServiceNautique(models.Model):
    type_service = models.CharField(max_length=50)  # pilotage, remorquage, lamanage...
    duree_moyenne_ref = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Service nautique"
        verbose_name_plural = "Services nautiques"

    def __str__(self):
        return self.type_service


class Calendrier(models.Model):
    date_calendaire = models.DateField(unique=True)
    mois = models.PositiveSmallIntegerField()
    trimestre = models.PositiveSmallIntegerField()
    annee = models.PositiveSmallIntegerField()
    jour_semaine = models.CharField(max_length=15)

    class Meta:
        verbose_name = "Calendrier"
        ordering = ["date_calendaire"]

    def __str__(self):
        return self.date_calendaire.isoformat()

    @classmethod
    def get_or_create_from_date(cls, date_obj):
        """Garantit l'existence de la ligne de dimension calendrier pour une date donnée."""
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        obj, _ = cls.objects.get_or_create(
            date_calendaire=date_obj,
            defaults={
                "mois": date_obj.month,
                "trimestre": (date_obj.month - 1) // 3 + 1,
                "annee": date_obj.year,
                "jour_semaine": jours[date_obj.weekday()],
            },
        )
        return obj


class Poste(models.Model):
    nom = models.CharField(max_length=80)
    longueur = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tirant_eau_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    terminal = models.ForeignKey(Terminal, on_delete=models.PROTECT, related_name="postes")

    class Meta:
        db_table = "poste"
        verbose_name = "Poste"

    def __str__(self):
        return self.nom


class Navire(models.Model):
    nom = models.CharField(max_length=150)
    imo = models.CharField("Numéro IMO", max_length=20, unique=True, null=True, blank=True)
    pavillon = models.CharField(max_length=60, blank=True)
    longueur = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    jauge_brute = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    type_navire = models.ForeignKey(TypeNavire, on_delete=models.PROTECT, related_name="navires")
    compagnie = models.ForeignKey(CompagnieMaritime, on_delete=models.PROTECT, related_name="navires")

    class Meta:
        verbose_name = "Navire"

    def __str__(self):
        return f"{self.nom} ({self.imo or 'IMO inconnu'})"

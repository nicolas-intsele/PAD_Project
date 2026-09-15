"""
Module 8 — Administration & Utilisateurs.

Modèles :
  - Role           : profil d'habilitation (Administrateur / Direction / Exploitation / Capitainerie)
  - ProfilUtilisateur : extension One-to-One du User Django (rôle, téléphone, actif)
  - JournalAction  : traçabilité de toutes les actions significatives des utilisateurs
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Role(models.Model):
    class Code(models.TextChoices):
        ADMIN        = "admin",        "Administrateur"
        DIRECTION    = "direction",    "Direction"
        EXPLOITATION = "exploitation", "Exploitation"
        CAPITAINERIE = "capitainerie", "Capitainerie"
        DAPC         = "dapc",         "DAPC"

    code        = models.CharField(max_length=20, choices=Code.choices, unique=True)
    libelle     = models.CharField(max_length=60)
    description = models.TextField(blank=True)
    permissions_kpi      = models.BooleanField(default=True,  help_text="Peut consulter les KPI")
    permissions_analytics= models.BooleanField(default=True,  help_text="Peut faire des analyses OLAP")
    permissions_alertes  = models.BooleanField(default=True,  help_text="Peut voir les alertes")
    permissions_reporting= models.BooleanField(default=True,  help_text="Peut générer des rapports")
    permissions_admin    = models.BooleanField(default=False, help_text="Accès à l'administration")

    class Meta:
        verbose_name = "Rôle"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.libelle

    @classmethod
    def initialiser_roles(cls):
        """Crée les 4 rôles du cahier des charges (idempotent)."""
        defaults = [
            {
                "code": cls.Code.ADMIN,
                "libelle": "Administrateur",
                "description": "Accès complet à toutes les fonctionnalités et à l'administration.",
                "permissions_kpi": True, "permissions_analytics": True,
                "permissions_alertes": True, "permissions_reporting": True,
                "permissions_admin": True,
            },
            {
                "code": cls.Code.DIRECTION,
                "libelle": "Direction",
                "description": "Vue stratégique : KPI globaux, tendances, comparaisons.",
                "permissions_kpi": True, "permissions_analytics": True,
                "permissions_alertes": True, "permissions_reporting": True,
                "permissions_admin": False,
            },
            {
                "code": cls.Code.EXPLOITATION,
                "libelle": "Exploitation",
                "description": "Vue opérationnelle : performance des postes, congestion, occupation.",
                "permissions_kpi": True, "permissions_analytics": True,
                "permissions_alertes": True, "permissions_reporting": True,
                "permissions_admin": False,
            },
            {
                "code": cls.Code.CAPITAINERIE,
                "libelle": "Capitainerie",
                "description": "Suivi des escales individuelles, retards, pilotage.",
                "permissions_kpi": True, "permissions_analytics": False,
                "permissions_alertes": True, "permissions_reporting": False,
                "permissions_admin": False,
            },
            {
                "code": cls.Code.DAPC,
                "libelle": "DAPC",
                "description": "Direction des Affaires Portuaires et de la Compétitivité : vue consolidée Direction + Exploitation.",
                "permissions_kpi": True, "permissions_analytics": True,
                "permissions_alertes": True, "permissions_reporting": True,
                "permissions_admin": False,
            },
        ]
        for d in defaults:
            cls.objects.update_or_create(code=d.pop("code"), defaults=d)


class ProfilUtilisateur(models.Model):
    utilisateur = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profil", primary_key=True
    )
    role        = models.ForeignKey(
        Role, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="utilisateurs"
    )
    telephone   = models.CharField(max_length=25, blank=True)
    poste       = models.CharField(max_length=100, blank=True)
    actif       = models.BooleanField(default=True)
    date_creation = models.DateTimeField(default=timezone.now, editable=False)
    derniere_connexion_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self) -> str:
        return f"{self.utilisateur.get_full_name() or self.utilisateur.username} ({self.role or 'sans rôle'})"

    @property
    def nom_affichage(self) -> str:
        return self.utilisateur.get_full_name() or self.utilisateur.username

    @property
    def role_code(self) -> str | None:
        return self.role.code if self.role else None


class JournalAction(models.Model):
    class TypeAction(models.TextChoices):
        CONNEXION      = "connexion",      "Connexion"
        DECONNEXION    = "deconnexion",    "Déconnexion"
        IMPORT_ETL     = "import_etl",     "Import ETL"
        CALCUL_KPI     = "calcul_kpi",     "Calcul KPI"
        GENERATION_RAPPORT = "generation_rapport", "Génération rapport"
        ACQUITTEMENT_ALERTE= "acquittement_alerte","Acquittement alerte"
        MODIFICATION_SEUIL = "modification_seuil", "Modification seuil"
        CREATION_USER  = "creation_user",  "Création utilisateur"
        MODIFICATION_USER = "modification_user", "Modification utilisateur"
        CONSULTATION   = "consultation",   "Consultation"
        AUTRE          = "autre",          "Autre"

    utilisateur = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="journal_actions"
    )
    type_action  = models.CharField(max_length=30, choices=TypeAction.choices)
    description  = models.TextField()
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    date_action  = models.DateTimeField(default=timezone.now)
    succes       = models.BooleanField(default=True)
    # Données contextuelles optionnelles (objet concerné)
    objet_type   = models.CharField(max_length=50, blank=True)
    objet_id     = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = "journal_action"
        verbose_name = "Journal d'action"
        verbose_name_plural = "Journal des actions"
        ordering = ["-date_action"]
        indexes = [
            models.Index(fields=["utilisateur", "date_action"]),
            models.Index(fields=["type_action"]),
        ]

    def __str__(self) -> str:
        user = self.utilisateur.username if self.utilisateur else "anonyme"
        return f"[{self.date_action:%d/%m/%Y %H:%M}] {user} — {self.type_action}"


# ── Fonction utilitaire de journalisation ────────────────────────────────────

def journaliser(request, type_action: str, description: str,
                succes: bool = True, objet_type: str = "", objet_id: str = "") -> None:
    """Crée une entrée dans le journal d'actions depuis n'importe quelle vue."""
    user = request.user if request.user.is_authenticated else None
    ip   = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR"))
    JournalAction.objects.create(
        utilisateur=user,
        type_action=type_action,
        description=description,
        ip_address=ip or None,
        succes=succes,
        objet_type=objet_type,
        objet_id=str(objet_id),
    )

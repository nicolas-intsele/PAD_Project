from django.conf import settings
from django.db import models


class JournalImport(models.Model):
    """Historisation de chaque import ETL (module Cahier des charges §1)."""

    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        SUCCES = "succes", "Succès"
        PARTIEL = "partiel", "Partiel (avec erreurs)"
        ECHEC = "echec", "Échec"

    source = models.CharField(max_length=255, help_text="Nom du fichier ou de la source importée")
    date_import = models.DateTimeField(auto_now_add=True)
    nb_lignes_lues = models.PositiveIntegerField(default=0)
    nb_lignes_chargees = models.PositiveIntegerField(default=0)
    nb_lignes_rejetees = models.PositiveIntegerField(default=0)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_COURS)
    erreurs = models.JSONField(default=list, blank=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="imports"
    )

    class Meta:
        verbose_name = "Journal d'import"
        verbose_name_plural = "Journaux d'import"
        ordering = ["-date_import"]

    def __str__(self):
        return f"Import {self.source} — {self.get_statut_display()} ({self.date_import:%Y-%m-%d %H:%M})"

    def marquer_succes(self, nb_chargees, nb_rejetees=None):
        self.nb_lignes_chargees = nb_chargees
        if nb_rejetees is not None:
            self.nb_lignes_rejetees = nb_rejetees
        self.statut = self.Statut.SUCCES if not self.erreurs else self.Statut.PARTIEL
        self.save(update_fields=["nb_lignes_lues", "nb_lignes_chargees", "nb_lignes_rejetees", "statut", "erreurs"])

    def marquer_echec(self):
        self.statut = self.Statut.ECHEC
        self.save(update_fields=["nb_lignes_lues", "nb_lignes_chargees", "nb_lignes_rejetees", "statut", "erreurs"])

    def ajouter_erreur(self, ligne, message, bloquant=False):
        """
        Enregistre une anomalie en mémoire (persistée lors de l'appel suivant à
        marquer_succes/marquer_echec). `bloquant=True` signale une ligne réellement
        exclue du chargement ; seules celles-ci sont comptabilisées dans nb_lignes_rejetees.
        """
        self.erreurs.append({"ligne": ligne, "message": message, "bloquant": bloquant})
        if bloquant:
            self.nb_lignes_rejetees += 1

"""Crée automatiquement un ProfilUtilisateur à chaque nouveau User Django."""
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ProfilUtilisateur


@receiver(post_save, sender=User)
def creer_profil(sender, instance, created, **kwargs):
    if created:
        ProfilUtilisateur.objects.get_or_create(utilisateur=instance)


@receiver(post_save, sender=User)
def sauvegarder_profil(sender, instance, **kwargs):
    try:
        instance.profil.save()
    except ProfilUtilisateur.DoesNotExist:
        ProfilUtilisateur.objects.create(utilisateur=instance)

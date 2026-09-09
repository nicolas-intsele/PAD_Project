"""
Moteur de détection des alertes — Module 6.

Deux sources d'anomalies scannées :
  1. KPI mensuels hors seuil  (via SeuilAlerte + ValeurKPI)
  2. Escales individuelles critiques (retard, attente longue, congestion)

Point d'entrée principal : ``scanner_alertes(date_debut, date_fin)``
Retourne le nombre d'alertes créées.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.escales.models import Escale
from apps.kpi.engine.calculateurs import (
    nombre_escales,
    taux_occupation_postes,
    temps_attente_moyen,
)
from apps.kpi.engine.service import calculer_kpi_mois
from apps.kpi.models import KPI, SeuilAlerte, ValeurKPI

from .models import Alerte

logger = logging.getLogger(__name__)

# ── Seuils intégrés (utilisés si aucun SeuilAlerte n'est paramétré) ──────────
SEUIL_ATTENTE_LONGUE_H   = 72    # temps d'attente individuel critique
SEUIL_CONGESTION_PCT     = 30    # taux de congestion global critique
SEUIL_OCCUPATION_PCT     = 85    # taux d'occupation des quais critique


# ─────────────────────────────────────────────────────────────────────────────
# 1. Alertes KPI (mensuel)
# ─────────────────────────────────────────────────────────────────────────────

def _alerte_existe(type_alerte: str, message_prefix: str, depuis: date) -> bool:
    """Évite de créer deux fois la même alerte sur la même période."""
    return Alerte.objects.filter(
        type_alerte=type_alerte,
        message__startswith=message_prefix,
        date_declenchement__date__gte=depuis,
        statut=Alerte.Statut.ACTIVE,
    ).exists()


def scanner_kpi_mensuels(annee: int, mois: int) -> int:
    """
    Pour chaque KPI avec au moins un SeuilAlerte défini, compare la valeur
    mensuelle calculée au seuil et crée une Alerte si dépassé.
    """
    creees = 0
    # Calcul (idempotent)
    resultats = calculer_kpi_mois(annee, mois)
    date_ref = date(annee, mois, 1)

    for seuil in SeuilAlerte.objects.select_related("kpi").all():
        valeur = resultats.get(seuil.kpi.code)
        if valeur is None:
            continue
        if not seuil.est_depasse(valeur):
            continue

        prefix = f"KPI {seuil.kpi.code} — {annee}-{mois:02d}"
        if _alerte_existe(Alerte.TypeAlerte.KPI_SEUIL, prefix, date_ref):
            continue

        direction = "supérieure" if (seuil.valeur_max and valeur > seuil.valeur_max) else "inférieure"
        borne     = seuil.valeur_max if direction == "supérieure" else seuil.valeur_min
        message   = (
            f"{prefix} : valeur {float(valeur):.2f} {seuil.kpi.unite or ''} "
            f"{direction} au seuil {float(borne):.2f} "
            f"(gravité : {seuil.niveau_gravite})"
        )
        Alerte.objects.create(
            seuil=seuil,
            type_alerte=Alerte.TypeAlerte.KPI_SEUIL,
            niveau_gravite=seuil.niveau_gravite,
            message=message,
            valeur_declenchante=Decimal(str(valeur)),
        )
        creees += 1
        logger.info("Alerte KPI créée : %s", message)

    return creees


# ─────────────────────────────────────────────────────────────────────────────
# 2. Alertes escales individuelles
# ─────────────────────────────────────────────────────────────────────────────

def scanner_escales_critiques(date_debut: date, date_fin: date) -> int:
    """
    Parcourt les escales de la période et crée des alertes pour :
      - temps d'attente individuel > SEUIL_ATTENTE_LONGUE_H
      - congestion globale > SEUIL_CONGESTION_PCT
      - taux d'occupation > SEUIL_OCCUPATION_PCT
    """
    creees = 0

def scanner_escales_critiques(date_debut: date, date_fin: date) -> int:
    """
    Parcourt les escales de la période et crée des alertes pour :
      - temps d'attente individuel > SEUIL_ATTENTE_LONGUE_H
      - congestion globale > SEUIL_CONGESTION_PCT
      - taux d'occupation > SEUIL_OCCUPATION_PCT
    """
    creees = 0

    # ── Retards individuels ──────────────────────────────────────────────────
    escales_en_retard = Escale.objects.filter(
        date_arrivee__date__range=(date_debut, date_fin),
        temps_attente__gt=SEUIL_ATTENTE_LONGUE_H,
        statut__in=[Escale.Statut.EN_COURS, Escale.Statut.TERMINEE],
    ).select_related("navire", "poste__terminal")

    # MO2 (audit Phase 7) : pré-chargement de toutes les alertes RETARD actives
    # de la période en UNE SEULE requête, au lieu d'une requête par escale dans la boucle.
    # Évite le N+1 qui posait problème à l'échelle du registre PAD réel.
    alertes_retard_existantes = set(
        Alerte.objects.filter(
            type_alerte=Alerte.TypeAlerte.RETARD,
            date_declenchement__date__gte=date_debut,
            statut=Alerte.Statut.ACTIVE,
        ).values_list("message", flat=True)
    )

    for escale in escales_en_retard:
        prefix = f"Retard escale #{escale.pk}"
        if any(msg.startswith(prefix) for msg in alertes_retard_existantes):
            continue
        message = (
            f"Retard escale #{escale.pk} — {escale.navire.nom} @ {escale.poste.terminal.nom} / {escale.poste.nom} "
            f"({escale.date_arrivee:%d/%m/%Y}) : temps d'attente {float(escale.temps_attente):.1f}h "
            f"(seuil : {SEUIL_ATTENTE_LONGUE_H}h)"
        )
        Alerte.objects.create(
            escale=escale,
            type_alerte=Alerte.TypeAlerte.RETARD,
            niveau_gravite="critique" if float(escale.temps_attente) > 96 else "avertissement",
            message=message,
            valeur_declenchante=escale.temps_attente,
        )
        alertes_retard_existantes.add(message)  # met à jour le cache en mémoire
        creees += 1

    # Congestion supprimée du catalogue KPI

    # ── Taux d'occupation des postes ─────────────────────────────────────────
    taux_occ = taux_occupation_postes(date_debut.year, date_debut.month)
    if taux_occ is not None and float(taux_occ) > SEUIL_OCCUPATION_PCT:
        prefix = f"Occupation postes {date_debut} → {date_fin}"
        if not _alerte_existe(Alerte.TypeAlerte.OCCUPATION, prefix, date_debut):
            message = (
                f"Taux d'occupation des postes : {float(taux_occ):.1f}% "
                f"sur {date_debut} → {date_fin} "
                f"(seuil : {SEUIL_OCCUPATION_PCT}%)"
            )
            Alerte.objects.create(
                type_alerte=Alerte.TypeAlerte.OCCUPATION,
                niveau_gravite="critique" if float(taux_occ) > 95 else "avertissement",
                message=message,
                valeur_declenchante=Decimal(str(taux_occ)),
            )
            creees += 1

    # ── Temps d'attente moyen global ─────────────────────────────────────────
    t_att = temps_attente_moyen(date_debut, date_fin)
    if t_att is not None and float(t_att) > SEUIL_ATTENTE_LONGUE_H:
        prefix = f"Attente moyenne {date_debut} → {date_fin}"
        if not _alerte_existe(Alerte.TypeAlerte.ATTENTE_LONGUE, prefix, date_debut):
            message = (
                f"Temps d'attente moyen global élevé : {float(t_att):.1f}h "
                f"sur {date_debut} → {date_fin} "
                f"(seuil : {SEUIL_ATTENTE_LONGUE_H}h)"
            )
            Alerte.objects.create(
                type_alerte=Alerte.TypeAlerte.ATTENTE_LONGUE,
                niveau_gravite="avertissement",
                message=message,
                valeur_declenchante=Decimal(str(t_att)),
            )
            creees += 1

    logger.info("Scan alertes %s → %s : %d créée(s)", date_debut, date_fin, creees)
    return creees


# ─────────────────────────────────────────────────────────────────────────────
# 3. Point d'entrée principal
# ─────────────────────────────────────────────────────────────────────────────

def scanner_alertes(date_debut: date | None = None, date_fin: date | None = None) -> dict:
    """
    Lance tous les scans d'alertes pour la période donnée.
    Par défaut : 30 derniers jours + mois en cours.
    """
    today = date.today()
    if date_debut is None:
        date_debut = today - timedelta(days=30)
    if date_fin is None:
        date_fin = today

    nb_kpi      = scanner_kpi_mensuels(today.year, today.month)
    nb_escales  = scanner_escales_critiques(date_debut, date_fin)

    return {
        "alertes_kpi":    nb_kpi,
        "alertes_escales": nb_escales,
        "total":          nb_kpi + nb_escales,
        "periode":        f"{date_debut} → {date_fin}",
    }


def stats_alertes() -> dict:
    """Statistiques rapides pour le badge sidebar et le centre d'alertes."""
    qs = Alerte.objects.all()
    return {
        "total_actives":   qs.filter(statut=Alerte.Statut.ACTIVE).count(),
        "critiques":       qs.filter(statut=Alerte.Statut.ACTIVE, niveau_gravite="critique").count(),
        "avertissements":  qs.filter(statut=Alerte.Statut.ACTIVE, niveau_gravite="avertissement").count(),
        "infos":           qs.filter(statut=Alerte.Statut.ACTIVE, niveau_gravite="info").count(),
        "resolues_7j":     qs.filter(
            statut=Alerte.Statut.RESOLUE,
            date_resolution__date__gte=date.today() - timedelta(days=7),
        ).count(),
    }

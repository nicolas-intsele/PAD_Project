"""
Moteur de calcul des KPI (Module 3).

Filtre de période : les KPI sont calculés par mois d'onglet source (mois_source).
Un navire arrivé en décembre mais enregistré dans l'onglet janvier compte
dans les KPI de janvier (Option B validée par le PAD).

Correspondance colonnes Excel → champs Escale :
  ARRIVEE RADE           → date_arrivee
  PILOTE A BORD ARRIVEE  → date_accostage
  NAVIRE ARRIVEE POSTE   → date_depart
  NAVIRE APPAREILLE      → date_appareillage
  PILOTE DEBARQUE ARRIVEE→ (utilisé pour temps_accostage)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal


def _arrondir(valeur, decimales=2):
    if valeur is None:
        return None
    return round(Decimal(str(valeur)), decimales)


def _qs_mois(annee: int, mois: int):
    """QuerySet de base filtré par mois_source (AAAA-MM)."""
    from apps.escales.models import Escale
    cle = f"{annee}-{mois:02d}"
    return Escale.objects.filter(mois_source=cle)


# ── KPI Trafic ────────────────────────────────────────────────────────────────

def nombre_escales(annee: int, mois: int) -> Decimal:
    """Nombre total d'escales enregistrées dans l'onglet du mois."""
    return Decimal(_qs_mois(annee, mois).count())


def nombre_arrivees(annee: int, mois: int) -> Decimal:
    """Nombre d'escales avec NAVIRE ARRIVEE POSTE renseigné."""
    return Decimal(_qs_mois(annee, mois).filter(date_depart__isnull=False).count())


def nombre_departs(annee: int, mois: int) -> Decimal:
    """Nombre d'escales avec NAVIRE APPAREILLE renseigné."""
    return Decimal(_qs_mois(annee, mois).filter(date_appareillage__isnull=False).count())


# ── KPI Temps ─────────────────────────────────────────────────────────────────

def temps_attente_moyen(annee: int, mois: int):
    """Moyenne de (PILOTE A BORD ARRIVEE − ARRIVEE RADE) en heures."""
    from django.db.models import Avg
    m = _qs_mois(annee, mois).filter(
        temps_attente__isnull=False
    ).aggregate(m=Avg("temps_attente"))["m"]
    return _arrondir(m)


def temps_sejour_moyen(annee: int, mois: int):
    """Moyenne de (NAVIRE APPAREILLE − NAVIRE ARRIVEE POSTE) en heures."""
    from django.db.models import Avg
    m = _qs_mois(annee, mois).filter(
        temps_sejour__isnull=False
    ).aggregate(m=Avg("temps_sejour"))["m"]
    return _arrondir(m)


def temps_pilotage_moyen(annee: int, mois: int):
    """Moyenne de (NAVIRE ARRIVEE POSTE − PILOTE A BORD ARRIVEE) en heures."""
    from django.db.models import Avg
    m = _qs_mois(annee, mois).filter(
        temps_pilotage__isnull=False
    ).aggregate(m=Avg("temps_pilotage"))["m"]
    return _arrondir(m)


def temps_accostage_moyen(annee: int, mois: int):
    """Moyenne de (PILOTE DEBARQUE ARRIVEE − NAVIRE ARRIVEE POSTE) en heures."""
    from django.db.models import Avg
    m = _qs_mois(annee, mois).filter(
        temps_accostage__isnull=False
    ).aggregate(m=Avg("temps_accostage"))["m"]
    return _arrondir(m)


# ── KPI Infrastructures ───────────────────────────────────────────────────────

def _heures_mois(annee: int, mois: int) -> float:
    import calendar
    return calendar.monthrange(annee, mois)[1] * 24


def taux_occupation_postes(annee: int, mois: int):
    """
    Taux d'occupation moyen des postes (%).
    Pour chaque poste actif : somme séjours / heures_mois × 100.
    Résultat = moyenne des taux de tous les postes actifs.
    """
    heures = _heures_mois(annee, mois)
    escales = list(_qs_mois(annee, mois).filter(
        temps_sejour__isnull=False
    ).values("poste_id", "temps_sejour"))

    if not escales:
        return None

    sejour_par_poste: dict[int, float] = {}
    for e in escales:
        pid = e["poste_id"]
        sejour_par_poste[pid] = sejour_par_poste.get(pid, 0) + float(e["temps_sejour"])

    taux = [min(s / heures * 100, 100) for s in sejour_par_poste.values()]
    return _arrondir(sum(taux) / len(taux))


def rotation_postes(annee: int, mois: int):
    """
    Rotation moyenne des postes (navires/poste).
    Nombre moyen de navires accostés par poste actif dans le mois.
    """
    escales = list(_qs_mois(annee, mois).values("poste_id"))
    if not escales:
        return None

    compteur: dict[int, int] = {}
    for e in escales:
        pid = e["poste_id"]
        compteur[pid] = compteur.get(pid, 0) + 1

    return _arrondir(sum(compteur.values()) / len(compteur))


# ── KPI Performance ───────────────────────────────────────────────────────────

def productivite(annee: int, mois: int):
    """
    Productivité moyenne (t/h).
    Moyenne de (tonnage_total / temps_sejour) pour chaque escale avec séjour > 0.
    """
    escales = list(_qs_mois(annee, mois).filter(
        temps_sejour__isnull=False,
    ).exclude(
        tonnage_debarque__isnull=True,
        tonnage_embarque__isnull=True,
    ).values("tonnage_debarque", "tonnage_embarque", "temps_sejour"))

    valeurs = []
    for e in escales:
        tonnage = float(e["tonnage_debarque"] or 0) + float(e["tonnage_embarque"] or 0)
        sejour = float(e["temps_sejour"])
        if sejour > 0 and tonnage > 0:
            valeurs.append(tonnage / sejour)

    if not valeurs:
        return None
    return _arrondir(sum(valeurs) / len(valeurs))


def debit_postes(annee: int, mois: int):
    """
    Débit moyen des postes (navires/jour d'occupation).
    Pour chaque poste actif : nb_navires / (somme_séjours_h / 24).
    Résultat = moyenne sur tous les postes avec séjour renseigné.
    """
    escales = list(_qs_mois(annee, mois).filter(
        temps_sejour__isnull=False,
    ).values("poste_id", "temps_sejour"))

    if not escales:
        return None

    sejour_par_poste: dict[int, float] = {}
    navires_par_poste: dict[int, int] = {}
    for e in escales:
        pid = e["poste_id"]
        sejour_par_poste[pid] = sejour_par_poste.get(pid, 0) + float(e["temps_sejour"])
        navires_par_poste[pid] = navires_par_poste.get(pid, 0) + 1

    valeurs = []
    for pid, sejour_h in sejour_par_poste.items():
        jours = sejour_h / 24
        if jours > 0:
            valeurs.append(navires_par_poste[pid] / jours)

    if not valeurs:
        return None
    return _arrondir(sum(valeurs) / len(valeurs))


# ── Registre ─────────────────────────────────────────────────────────────────

CALCULATEURS = {
    "TRAFIC_NB_ESCALES":     nombre_escales,
    "TRAFIC_NB_ARRIVEES":    nombre_arrivees,
    "TRAFIC_NB_DEPARTS":     nombre_departs,
    "TEMPS_ATTENTE_MOYEN":   temps_attente_moyen,
    "TEMPS_SEJOUR_MOYEN":    temps_sejour_moyen,
    "TEMPS_PILOTAGE_MOYEN":  temps_pilotage_moyen,
    "TEMPS_ACCOSTAGE_MOYEN": temps_accostage_moyen,
    "INFRA_TAUX_OCCUPATION": taux_occupation_postes,
    "INFRA_ROTATION_POSTES": rotation_postes,
    "PERF_PRODUCTIVITE":     productivite,
    "PERF_DEBIT_POSTES":     debit_postes,
}

# Alias pour compatibilité avec les appels directs depuis les vues
SEUIL_CONGESTION_HEURES = 48

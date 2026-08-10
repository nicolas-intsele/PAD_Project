"""
Chargement des données nettoyées dans l'entrepôt de données (Module 2).

Résout ou crée les lignes de dimension (Navire, Quai, Terminal...) puis
insère les lignes de la table de faits ESCALE, en s'appuyant sur le
Modèle Physique de Données (voir docs/MCD_MLD_MPD_PAD.docx).
"""
from __future__ import annotations

import pandas as pd
from django.db import transaction

from apps.escales.models import Escale
from apps.referentiel.models import (
    AgentMaritime,
    Calendrier,
    CompagnieMaritime,
    Navire,
    Quai,
    Terminal,
    TypeNavire,
)


def _sanitize(valeur):
    """Convertit toute valeur manquante pandas (NaT, NaN, None) en None Python."""
    try:
        if valeur is None or pd.isna(valeur):
            return None
    except (TypeError, ValueError):
        pass
    return valeur


def _duree_heures(debut, fin):
    """Retourne la durée en heures entre deux datetimes, ou None si l'une des deux manque."""
    debut, fin = _sanitize(debut), _sanitize(fin)
    if debut is None or fin is None:
        return None
    delta = fin - debut
    heures = delta.total_seconds() / 3600
    return round(heures, 2) if heures >= 0 else None


class EscaleLoader:
    """Charge un DataFrame nettoyé dans les tables NAVIRE / QUAI / ... / ESCALE."""

    def __init__(self, journal_import=None):
        self.journal_import = journal_import

    def charger(self, df: pd.DataFrame, lignes_ignorees: set[int] | None = None):
        """
        Charge chaque ligne valide du DataFrame. Retourne (nb_chargees, erreurs).
        `lignes_ignorees` : index de lignes (base pandas +2) déjà rejetées par le contrôle qualité.
        """
        lignes_ignorees = lignes_ignorees or set()
        nb_chargees = 0
        erreurs = []

        for idx, row in df.iterrows():
            numero_ligne = idx + 2
            if numero_ligne in lignes_ignorees:
                continue
            try:
                with transaction.atomic():
                    self._charger_ligne(row)
                nb_chargees += 1
            except Exception as exc:  # noqa: BLE001 - on isole l'erreur par ligne
                erreurs.append({"ligne": numero_ligne, "message": str(exc)})

        return nb_chargees, erreurs

    # ------------------------------------------------------------------ #
    def _resoudre_navire(self, row, type_navire, compagnie) -> Navire:
        """
        Résout (ou crée) le Navire correspondant à la ligne.

        Environ 10% des navires du référentiel officiel du PAD n'ont pas
        de numéro IMO renseigné : dans ce cas, on identifie le navire par
        son nom (insensible à la casse) plutôt que par une clé IMO absente,
        pour éviter toute collision entre navires distincts sans IMO.
        """
        imo = (row.get("navire_imo") or "").strip() or None
        nom = row["navire_nom"]
        defaults = {
            "nom": nom,
            "pavillon": row.get("pavillon") or "",
            "longueur": row.get("longueur_navire"),
            "jauge_brute": row.get("jauge_brute"),
            "type_navire": type_navire,
            "compagnie": compagnie,
        }

        if imo:
            navire, _ = Navire.objects.update_or_create(imo=imo, defaults=defaults)
            return navire

        navire = Navire.objects.filter(imo__isnull=True, nom__iexact=nom).first()
        if navire is None:
            navire = Navire.objects.create(imo=None, **defaults)
        else:
            for champ, valeur in defaults.items():
                setattr(navire, champ, valeur)
            navire.save(update_fields=list(defaults.keys()))
        return navire

    def _charger_ligne(self, row) -> Escale:
        terminal, _ = Terminal.objects.get_or_create(nom=row["terminal"])
        quai, _ = Quai.objects.get_or_create(nom=row["quai"], terminal=terminal)

        type_navire, _ = TypeNavire.objects.get_or_create(libelle=row.get("type_navire") or "Non renseigné")
        compagnie, _ = CompagnieMaritime.objects.get_or_create(raison_sociale=row["compagnie"])
        agent, _ = AgentMaritime.objects.get_or_create(nom=row["agent_maritime"])

        navire = self._resoudre_navire(row, type_navire, compagnie)

        date_arrivee = row["date_arrivee"]
        date_ref = Calendrier.get_or_create_from_date(date_arrivee.date())

        escale, _ = Escale.objects.update_or_create(
            navire=navire,
            quai=quai,
            date_arrivee=date_arrivee,
            defaults={
                "agent": agent,
                "date_ref": date_ref,
                "date_accostage": _sanitize(row.get("date_accostage")),
                "date_appareillage": _sanitize(row.get("date_appareillage")),
                "date_depart": _sanitize(row.get("date_depart")),
                "statut": row.get("statut") or Escale.Statut.PLANIFIEE,
                "import_source": self.journal_import,
            },
        )

        # Calcul immédiat des temps caractéristiques lorsque les dates sont disponibles
        escale.temps_attente = escale.calculer_temps_attente()
        escale.temps_sejour = escale.calculer_duree_sejour()

        # Si la source fournit le détail des opérations de pilotage (colonnes
        # optionnelles pilote_arrivee_debut/fin, pilote_depart_debut/fin), on
        # calcule des temps plus précis que les seules dates d'arrivée/accostage/départ.
        if "pilote_arrivee_debut" in row.index:
            temps_pilotage_arrivee = _duree_heures(row.get("pilote_arrivee_debut"), row.get("pilote_arrivee_fin"))
            temps_pilotage_depart = _duree_heures(row.get("pilote_depart_debut"), row.get("pilote_depart_fin"))
            if temps_pilotage_arrivee is not None or temps_pilotage_depart is not None:
                escale.temps_pilotage = round(
                    (temps_pilotage_arrivee or 0) + (temps_pilotage_depart or 0), 2
                )
            escale.temps_accostage = _duree_heures(row.get("pilote_arrivee_debut"), row.get("date_accostage"))

        escale.save(update_fields=["temps_attente", "temps_sejour", "temps_pilotage", "temps_accostage"])

        return escale

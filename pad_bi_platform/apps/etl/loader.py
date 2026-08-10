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
    def _charger_ligne(self, row) -> Escale:
        terminal, _ = Terminal.objects.get_or_create(nom=row["terminal"])
        quai, _ = Quai.objects.get_or_create(nom=row["quai"], terminal=terminal)

        type_navire, _ = TypeNavire.objects.get_or_create(libelle=row.get("type_navire") or "Non renseigné")
        compagnie, _ = CompagnieMaritime.objects.get_or_create(raison_sociale=row["compagnie"])
        agent, _ = AgentMaritime.objects.get_or_create(nom=row["agent_maritime"])

        navire, _ = Navire.objects.update_or_create(
            imo=row["navire_imo"] or None,
            defaults={
                "nom": row["navire_nom"],
                "pavillon": row.get("pavillon") or "",
                "longueur": row.get("longueur_navire"),
                "jauge_brute": row.get("jauge_brute"),
                "type_navire": type_navire,
                "compagnie": compagnie,
            },
        )

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
        escale.save(update_fields=["temps_attente", "temps_sejour"])

        return escale

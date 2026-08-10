"""
Contrôle qualité des données brutes avant transformation/chargement.

Ce module implémente la fonctionnalité "Contrôle qualité" du Module 1
(Collecte et intégration des données) du cahier des charges : vérification
des formats, détection des doublons et des valeurs manquantes.
"""
from __future__ import annotations

import pandas as pd

# Colonnes attendues dans un fichier d'import d'escales (CSV ou Excel)
COLONNES_REQUISES = [
    "navire_nom",
    "type_navire",
    "compagnie",
    "agent_maritime",
    "quai",
    "terminal",
    "date_arrivee",
]

COLONNES_OPTIONNELLES = [
    "navire_imo",
    "pavillon",
    "longueur_navire",
    "jauge_brute",
    "date_accostage",
    "date_appareillage",
    "date_depart",
    "statut",
]

COLONNES_DATE = ["date_arrivee", "date_accostage", "date_appareillage", "date_depart"]


class QualityIssue:
    """Représente une anomalie détectée sur une ligne du fichier source."""

    def __init__(self, ligne: int, champ: str, message: str, bloquant: bool = True):
        self.ligne = ligne
        self.champ = champ
        self.message = message
        self.bloquant = bloquant

    def to_dict(self):
        return {"ligne": self.ligne, "champ": self.champ, "message": self.message, "bloquant": self.bloquant}

    def __repr__(self):
        return f"<QualityIssue ligne={self.ligne} champ={self.champ} '{self.message}'>"


class QualityReport:
    """Rapport de contrôle qualité pour un import donné."""

    def __init__(self):
        self.issues: list[QualityIssue] = []

    def add(self, issue: QualityIssue):
        self.issues.append(issue)

    @property
    def is_valid(self) -> bool:
        """Le fichier est jugé exploitable s'il ne contient aucune anomalie bloquante."""
        return not any(i.bloquant for i in self.issues)

    @property
    def blocking_lines(self) -> set[int]:
        return {i.ligne for i in self.issues if i.bloquant}

    def to_list(self):
        return [i.to_dict() for i in self.issues]

    def summary(self) -> str:
        nb_bloquantes = sum(1 for i in self.issues if i.bloquant)
        nb_avert = len(self.issues) - nb_bloquantes
        return f"{nb_bloquantes} anomalie(s) bloquante(s), {nb_avert} avertissement(s)"


class DataQualityController:
    """
    Contrôleur qualité appliqué à un DataFrame pandas issu de l'extraction
    d'un fichier CSV/Excel, avant nettoyage et chargement.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def controler(self) -> QualityReport:
        report = QualityReport()
        self._controler_colonnes(report)
        # Si des colonnes obligatoires manquent, inutile de poursuivre ligne à ligne
        if report.is_valid:
            self._controler_valeurs_manquantes(report)
            self._controler_formats_dates(report)
            self._controler_doublons(report)
            self._controler_coherence_dates(report)
        return report

    # ------------------------------------------------------------------ #
    def _controler_colonnes(self, report: QualityReport):
        colonnes_absentes = [c for c in COLONNES_REQUISES if c not in self.df.columns]
        for col in colonnes_absentes:
            report.add(QualityIssue(ligne=0, champ=col, message=f"Colonne obligatoire absente : {col}"))

    def _controler_valeurs_manquantes(self, report: QualityReport):
        for col in COLONNES_REQUISES:
            manquants = self.df[self.df[col].isna() | (self.df[col].astype(str).str.strip() == "")]
            for idx in manquants.index:
                report.add(QualityIssue(
                    ligne=idx + 2,  # +2 : ligne 1 = en-tête, index pandas base 0
                    champ=col,
                    message=f"Valeur manquante pour le champ obligatoire '{col}'",
                ))

    def _controler_formats_dates(self, report: QualityReport):
        for col in COLONNES_DATE:
            if col not in self.df.columns:
                continue
            for idx, val in self.df[col].items():
                if pd.isna(val) or str(val).strip() == "":
                    continue
                parsed = pd.to_datetime(val, errors="coerce", dayfirst=True)
                if pd.isna(parsed):
                    report.add(QualityIssue(
                        ligne=idx + 2,
                        champ=col,
                        message=f"Format de date invalide : '{val}'",
                    ))

    def _controler_doublons(self, report: QualityReport):
        cle = ["navire_nom", "quai", "date_arrivee"]
        cle_presente = [c for c in cle if c in self.df.columns]
        if len(cle_presente) < len(cle):
            return
        doublons = self.df[self.df.duplicated(subset=cle_presente, keep=False)]
        for idx in doublons.index:
            report.add(QualityIssue(
                ligne=idx + 2,
                champ="+".join(cle_presente),
                message="Doublon détecté (même navire, quai et date d'arrivée)",
                bloquant=False,  # avertissement : traité comme mise à jour, non rejeté
            ))

    def _controler_coherence_dates(self, report: QualityReport):
        SEUIL_SEJOUR_SUSPECT_HEURES = 720  # 30 jours : au-delà, on signale sans bloquer

        for idx, row in self.df.iterrows():
            arrivee = pd.to_datetime(row.get("date_arrivee"), errors="coerce", dayfirst=True)
            if pd.isna(arrivee):
                continue

            accostage = pd.to_datetime(row.get("date_accostage"), errors="coerce", dayfirst=True) \
                if row.get("date_accostage") not in (None, "") else None
            depart = pd.to_datetime(row.get("date_depart"), errors="coerce", dayfirst=True) \
                if row.get("date_depart") not in (None, "") else None

            if accostage is not None and pd.notna(accostage) and accostage < arrivee:
                report.add(QualityIssue(
                    ligne=idx + 2,
                    champ="date_accostage",
                    message="L'accostage précède l'arrivée du navire (temps d'attente négatif)",
                ))

            if depart is not None and pd.notna(depart):
                if depart < arrivee:
                    report.add(QualityIssue(
                        ligne=idx + 2,
                        champ="date_depart",
                        message="La date de départ précède la date d'arrivée",
                    ))
                else:
                    duree_h = (depart - arrivee).total_seconds() / 3600
                    if duree_h > SEUIL_SEJOUR_SUSPECT_HEURES:
                        report.add(QualityIssue(
                            ligne=idx + 2,
                            champ="date_depart",
                            message=f"Durée de séjour anormalement élevée ({duree_h:.0f} h) — à vérifier",
                            bloquant=False,
                        ))

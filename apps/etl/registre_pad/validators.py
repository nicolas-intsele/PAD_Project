"""Contrôle qualité adapté au schéma réel du registre mensuel des escales du PAD."""
from __future__ import annotations

import pandas as pd

from apps.etl.validators import QualityIssue, QualityReport

from .dateutils import parser_date_intelligent
from .mapping import COLONNES_DATE_ESCALES, COLONNES_REQUISES_ESCALES


class RegistrePADQualityController:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def controler(self) -> QualityReport:
        report = QualityReport()
        self._controler_valeurs_manquantes(report)
        self._controler_formats_dates(report)
        self._controler_doublons(report)
        self._controler_coherence_dates(report)
        return report

    def _ligne(self, idx) -> int:
        return int(self.df.loc[idx, "ligne_source"])

    def _controler_valeurs_manquantes(self, report: QualityReport):
        for col in COLONNES_REQUISES_ESCALES:
            manquants = self.df[self.df[col].isna() | (self.df[col].astype(str).str.strip() == "")]
            for idx in manquants.index:
                report.add(QualityIssue(
                    ligne=self._ligne(idx), champ=col,
                    message=f"Valeur manquante pour le champ obligatoire '{col}' ({self.df.loc[idx, 'mois_source']})",
                ))

    def _controler_formats_dates(self, report: QualityReport):
        for col in COLONNES_DATE_ESCALES:
            for idx, val in self.df[col].items():
                if pd.isna(val) or str(val).strip() == "":
                    continue
                parsed = parser_date_intelligent(val)
                if parsed is None:
                    bloquant = col in COLONNES_REQUISES_ESCALES
                    report.add(QualityIssue(
                        ligne=self._ligne(idx), champ=col,
                        message=f"Format de date invalide : '{val}'", bloquant=bloquant,
                    ))

    def _controler_doublons(self, report: QualityReport):
        cle = ["navire", "poste", "arrivee_rade"]
        doublons = self.df[self.df.duplicated(subset=cle, keep=False)]
        for idx in doublons.index:
            report.add(QualityIssue(
                ligne=self._ligne(idx), champ="+".join(cle),
                message="Doublon détecté (même navire, poste et heure d'arrivée en rade)",
                bloquant=False,
            ))

    def _controler_coherence_dates(self, report: QualityReport):
        for idx, row in self.df.iterrows():
            rade = parser_date_intelligent(row.get("arrivee_rade"))
            poste = parser_date_intelligent(row.get("arrivee_poste"))
            appareillage = parser_date_intelligent(row.get("navire_appareille"))
            depart_pilote = parser_date_intelligent(row.get("pilote_debarque_depart"))
            if rade is not None and poste is not None and poste < rade:
                report.add(QualityIssue(
                    ligne=self._ligne(idx), champ="arrivee_poste",
                    message="L'accostage précède l'arrivée en rade", bloquant=False,
                ))
            if poste is not None and appareillage is not None and appareillage < poste:
                report.add(QualityIssue(
                    ligne=self._ligne(idx), champ="navire_appareille",
                    message="L'appareillage précède l'accostage", bloquant=False,
                ))
            depart_final = depart_pilote or appareillage
            if rade is not None and depart_final is not None and depart_final < rade:
                report.add(QualityIssue(
                    ligne=self._ligne(idx), champ="pilote_debarque_depart",
                    message=(
                        "Le départ du navire précède son arrivée en rade (dates probablement "
                        "erronées à la saisie) — temps de séjour non calculé pour cette escale"
                    ),
                    bloquant=False,
                ))

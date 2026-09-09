"""
Extraction du classeur "Registre mensuel des escales" du PAD :
un onglet par mois (double en-tête) + deux onglets de référence.
"""
from __future__ import annotations

import pandas as pd

from .mapping import (
    COLONNES_ESCALES,
    COLONNES_NAVIRES_REF,
    NB_COLONNES_ESCALES,
    ONGLET_AUTRES,
    ONGLET_NAVIRES,
    ONGLETS_MOIS,
)


def extraire_escales(fichier) -> pd.DataFrame:
    """
    Lit tous les onglets mensuels non vides et retourne un unique DataFrame
    concaténé, avec les colonnes canoniques de mapping.COLONNES_ESCALES et
    une colonne supplémentaire 'mois_source' pour la traçabilité.

    Les onglets futurs sans données (aucune ligne sous les 2 lignes d'en-tête)
    sont ignorés silencieusement : c'est un comportement normal du registre
    (mois non encore renseignés).
    """
    xls = pd.ExcelFile(fichier, engine="openpyxl")
    morceaux = []

    for onglet in ONGLETS_MOIS:
        if onglet not in xls.sheet_names:
            continue
        df = pd.read_excel(xls, sheet_name=onglet, header=None, skiprows=2, dtype=str)
        if df.empty:
            continue
        df = df.iloc[:, :NB_COLONNES_ESCALES]
        df.columns = COLONNES_ESCALES
        df = df[df["navire"].notna() & (df["navire"].astype(str).str.strip() != "")]
        if df.empty:
            continue
        df = df.reset_index(drop=True)
        df["mois_source"] = onglet.strip()
        df["ligne_source"] = df.index + 3  # +2 en-têtes +1 base Excel (ligne 1)
        morceaux.append(df)

    if not morceaux:
        return pd.DataFrame(columns=COLONNES_ESCALES + ["mois_source", "ligne_source"])

    return pd.concat(morceaux, ignore_index=True)


def extraire_navires_reference(fichier) -> pd.DataFrame:
    """Lit l'onglet DONNEES DES NAVIRES (référentiel navires du PAD)."""
    df = pd.read_excel(fichier, sheet_name=ONGLET_NAVIRES, engine="openpyxl", dtype=str)
    df.columns = COLONNES_NAVIRES_REF
    df = df[df["navire"].notna() & (df["navire"].astype(str).str.strip() != "")]
    return df.reset_index(drop=True)


def extraire_postes_reference(fichier) -> pd.DataFrame:
    """
    Lit l'onglet AUTRES DONNEES et retourne la correspondance POSTE -> SPECIALITE
    (utilisée comme proxy du couple POSTE/TERMINAL en l'absence d'un référentiel dédié).
    """
    df = pd.read_excel(fichier, sheet_name=ONGLET_AUTRES, engine="openpyxl", header=None, skiprows=2, dtype=str)
    postes = df.iloc[:, [0, 1]].copy()
    postes.columns = ["specialite", "poste"]
    postes = postes[postes["poste"].notna() & (postes["poste"].astype(str).str.strip() != "")]
    postes["specialite"] = postes["specialite"].where(postes["specialite"].notna(), "Non spécifié")
    return postes.reset_index(drop=True)

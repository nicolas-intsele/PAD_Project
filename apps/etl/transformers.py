"""
Nettoyage et transformation des données brutes (Module 1 du cahier des charges).

Normalise les libellés, les dates et les unités avant chargement dans
l'entrepôt de données.
"""
from __future__ import annotations

import pandas as pd
from django.utils import timezone


def _normaliser_texte(valeur) -> str:
    if pd.isna(valeur):
        return ""
    return str(valeur).strip()


def _normaliser_titre(valeur) -> str:
    texte = _normaliser_texte(valeur)
    return texte.title() if texte else texte


def _parser_date(valeur):
    if valeur is None or pd.isna(valeur) or str(valeur).strip() == "":
        return None
    parsed = pd.to_datetime(valeur, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    dt = parsed.to_pydatetime()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_default_timezone())
    return dt


def _parser_decimal(valeur):
    if valeur is None or pd.isna(valeur) or str(valeur).strip() == "":
        return None
    try:
        # tolère la virgule décimale (saisie française)
        return float(str(valeur).replace(",", "."))
    except ValueError:
        return None


def nettoyer_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Retourne une copie nettoyée et normalisée du DataFrame :
    - textes : nettoyage des espaces, casse homogène
    - dates : parsing tolérant (jj/mm/aaaa ou aaaa-mm-jj)
    - nombres : tolérance à la virgule décimale française
    """
    df = df.copy()

    colonnes_texte = ["navire_imo", "navire_nom", "type_navire", "compagnie",
                       "agent_maritime", "poste", "terminal", "pavillon", "statut"]
    for col in colonnes_texte:
        if col in df.columns:
            df[col] = df[col].apply(_normaliser_texte)

    for col in ["navire_nom", "compagnie", "agent_maritime", "poste", "terminal"]:
        if col in df.columns:
            df[col] = df[col].apply(_normaliser_titre)

    if "navire_imo" in df.columns:
        df["navire_imo"] = df["navire_imo"].str.upper()

    for col in ["date_arrivee", "date_accostage", "date_appareillage", "date_depart"]:
        if col in df.columns:
            # dtype=object explicite : évite que pandas ne reconvertisse silencieusement
            # les None en NaT lorsque la colonne est castée en datetime64.
            df[col] = df[col].apply(_parser_date).astype(object)
            df[col] = df[col].where(df[col].notna(), None)

    for col in ["longueur_navire", "jauge_brute"]:
        if col in df.columns:
            df[col] = df[col].apply(_parser_decimal)

    if "statut" in df.columns:
        df["statut"] = df["statut"].str.lower().replace({
            "": "planifiee", "planifiée": "planifiee", "en cours": "en_cours",
            "terminée": "terminee", "annulée": "annulee",
        })

    return df

"""
Analyse des dates du registre PAD.

Le classeur source mélange deux origines de dates dans les mêmes colonnes :
- des cellules Excel réellement typées "date" (grande majorité), que
  l'extraction (dtype=str) restitue sous forme de chaîne ISO non ambiguë
  ("2026-01-04 08:00:00") ;
- des saisies manuelles au format français JJ/MM/AAAA (une minorité,
  provenant visiblement d'un copier-coller ou d'une correction manuelle),
  qui restent ambiguës hors contexte ("11/01/2026 16:30").

Appliquer dayfirst=True uniformément corromprait les dates ISO (pandas
interprète alors "2026-01-04" comme le 4e mois plutôt que le 4e jour).
Cette fonction détecte le format et n'active dayfirst que pour les dates
au format JJ/MM/AAAA.
"""
from __future__ import annotations

import re

import pandas as pd

_ISO_PREFIX = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}")


def parser_date_intelligent(valeur):
    if valeur is None or pd.isna(valeur):
        return None
    texte = str(valeur).strip()
    if texte == "":
        return None
    dayfirst = _ISO_PREFIX.match(texte) is None
    parsed = pd.to_datetime(texte, errors="coerce", dayfirst=dayfirst)
    return None if pd.isna(parsed) else parsed

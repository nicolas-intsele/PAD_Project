"""Interface commune à tous les importeurs de sources de données (CSV, Excel, Oracle...)."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseImporter(ABC):
    """
    Toute source de données (fichier ou future connexion Oracle) doit exposer
    une méthode extract() retournant un DataFrame pandas au schéma commun
    défini dans etl.validators.COLONNES_REQUISES / COLONNES_OPTIONNELLES.
    """

    @abstractmethod
    def extract(self, source) -> pd.DataFrame:
        """Lit la source et retourne un DataFrame brut (non validé, non nettoyé)."""
        raise NotImplementedError

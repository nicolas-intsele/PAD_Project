import pandas as pd

from .base import BaseImporter


class ExcelImporter(BaseImporter):
    """Import de fichiers Excel .xlsx (Module 1 — Collecte et intégration des données)."""

    def __init__(self, sheet_name=0):
        self.sheet_name = sheet_name

    def extract(self, source) -> pd.DataFrame:
        """`source` : chemin de fichier, objet fichier ou UploadedFile Django."""
        df = pd.read_excel(source, sheet_name=self.sheet_name, engine="openpyxl", dtype=str)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df

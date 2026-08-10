import pandas as pd

from .base import BaseImporter


class CSVImporter(BaseImporter):
    """Import de fichiers CSV (Module 1 — Collecte et intégration des données)."""

    def __init__(self, delimiter: str = ",", encoding: str = "utf-8"):
        self.delimiter = delimiter
        self.encoding = encoding

    def extract(self, source) -> pd.DataFrame:
        """
        `source` : chemin de fichier, objet fichier ou UploadedFile Django.
        Tente automatiquement le délimiteur ';' si ',' ne produit qu'une seule colonne
        (cas fréquent des exports Excel en français).
        """
        df = pd.read_csv(source, delimiter=self.delimiter, encoding=self.encoding, dtype=str)
        if df.shape[1] == 1:
            if hasattr(source, "seek"):
                source.seek(0)
            df = pd.read_csv(source, delimiter=";", encoding=self.encoding, dtype=str)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df

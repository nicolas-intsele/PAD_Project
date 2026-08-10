from rest_framework import serializers

from .models import JournalImport


class JournalImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalImport
        fields = [
            "id", "source", "date_import", "nb_lignes_lues", "nb_lignes_chargees",
            "nb_lignes_rejetees", "statut", "erreurs", "utilisateur",
        ]
        read_only_fields = fields


class ImportUploadSerializer(serializers.Serializer):
    fichier = serializers.FileField()
    format = serializers.ChoiceField(choices=["csv", "excel"], required=False)

    def validate(self, attrs):
        fichier = attrs["fichier"]
        if "format" not in attrs:
            suffix = fichier.name.lower().rsplit(".", 1)[-1]
            attrs["format"] = "excel" if suffix in ("xlsx", "xls") else "csv"
        return attrs

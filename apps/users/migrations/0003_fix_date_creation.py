from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_alter_role_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profilutilisateur",
            name="date_creation",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                editable=False,
            ),
        ),
    ]

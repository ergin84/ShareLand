# Generated migration for adding id_archaeological_evidence field to Image model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('frontend', '0010_add_evidence_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='image',
            name='id_archaeological_evidence',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='frontend.archaeologicalevidence', db_column='id_archaeological_evidence'),
        ),
    ]

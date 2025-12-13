from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('frontend', '0009_add_user_to_author'),
    ]

    operations = [
        migrations.AddField(
            model_name='archaeologicalevidence',
            name='evidence_name',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]

# Generated migration to remove Author model
# This table has been consolidated into User/Profile (single source of truth)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('frontend', '0014_consolidate_author_into_user'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Author',
        ),
    ]

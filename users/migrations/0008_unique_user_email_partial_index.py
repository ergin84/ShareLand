# Generated migration to add partial unique constraint for non-empty emails

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_unique_user_email'),
    ]

    operations = [
        # Add a partial unique constraint: unique WHERE email != ''
        # This allows multiple empty emails but enforces uniqueness on actual email addresses
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX auth_user_email_unique_non_empty ON auth_user(email) WHERE email != '';",
            reverse_sql="DROP INDEX IF EXISTS auth_user_email_unique_non_empty;",
        ),
    ]

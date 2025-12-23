from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_profile_affiliation_profile_name_profile_orcid_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='profile',
            name='name',
        ),
        migrations.RemoveField(
            model_name='profile',
            name='surname',
        ),
        migrations.AddField(
            model_name='profile',
            name='contact_email',
            field=models.EmailField(blank=True, null=True, help_text='Alternative contact email for research/author purposes'),
        ),
        migrations.AddField(
            model_name='profile',
            name='id_anagraphic',
            field=models.IntegerField(blank=True, null=True, help_text='Legacy anagraphic ID from imported data'),
        ),
    ]

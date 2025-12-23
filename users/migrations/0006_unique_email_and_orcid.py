# Generated migration to add unique constraints for email and orcid
# With deduplication for empty/null and duplicate orcid values

from django.db import migrations, models
from django.db.models import Count


def deduplicate_orcid(apps, schema_editor):
    """Remove duplicate orcid values to allow unique constraint"""
    Profile = apps.get_model('users', 'Profile')
    
    # Find all duplicate orcid values (including NULL/empty)
    duplicates = Profile.objects.values('orcid').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    for dup in duplicates:
        orcid_val = dup['orcid']
        profiles = Profile.objects.filter(orcid=orcid_val).order_by('id')
        
        # Keep the first one, clear the rest
        for profile in list(profiles)[1:]:
            profile.orcid = None
            profile.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_populate_user_roles'),
    ]

    operations = [
        migrations.RunPython(deduplicate_orcid),
        # Add unique constraint to Profile.orcid
        migrations.AlterField(
            model_name='profile',
            name='orcid',
            field=models.CharField(blank=True, help_text='ORCID ID (e.g., 0000-0000-0000-0000)', max_length=19, null=True, unique=True),
        ),
    ]

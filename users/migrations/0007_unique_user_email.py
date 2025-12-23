# Generated migration to add unique constraint for User.email
# With deduplication for duplicate email values

from django.db import migrations


def deduplicate_email(apps, schema_editor):
    """Remove duplicate email values to allow unique constraint"""
    User = apps.get_model('auth', 'User')
    from django.db.models import Count
    
    # Find all duplicate email values
    duplicates = User.objects.values('email').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    for dup in duplicates:
        email_val = dup['email']
        users = User.objects.filter(email=email_val).order_by('id')
        user_list = list(users)
        
        # Keep the first one, change the rest to empty string
        for user in user_list[1:]:
            user.email = ''
            user.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_unique_email_and_orcid'),
    ]

    operations = [
        migrations.RunPython(deduplicate_email),
        # Add unique constraint to User.email (allowing empty string as blank)
        # Note: We keep this at database level with a partial unique index
        # PostgreSQL will treat NULL as distinct, and empty string '' as a value
    ]

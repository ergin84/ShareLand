from django.db import migrations


def create_default_roles(apps, schema_editor):
    """Create default user roles"""
    UserRole = apps.get_model('users', 'UserRole')
    
    default_roles = [
        {
            'role': 'user',
            'description': 'Basic user account with minimal permissions',
            'permissions': 'view_profile, edit_own_profile'
        },
        {
            'role': 'author',
            'description': 'User who creates and manages research projects',
            'permissions': 'create_research, edit_own_research, submit_research, view_research'
        },
        {
            'role': 'researcher',
            'description': 'User conducting research with advanced permissions',
            'permissions': 'create_research, edit_own_research, view_all_research, collaborate'
        },
        {
            'role': 'contributor',
            'description': 'User who contributes to research and data',
            'permissions': 'contribute_data, edit_contributed_data, view_research'
        },
        {
            'role': 'moderator',
            'description': 'User who moderates content and users',
            'permissions': 'moderate_content, moderate_users, view_reports'
        },
        {
            'role': 'admin',
            'description': 'Full administrator with all permissions',
            'permissions': 'all'
        },
    ]
    
    for role_data in default_roles:
        UserRole.objects.get_or_create(
            role=role_data['role'],
            defaults={
                'description': role_data['description'],
                'permissions': role_data['permissions'],
                'is_active': True
            }
        )


def reverse_create_default_roles(apps, schema_editor):
    """Delete default user roles"""
    UserRole = apps.get_model('users', 'UserRole')
    UserRole.objects.filter(role__in=['user', 'author', 'researcher', 'contributor', 'moderator', 'admin']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_add_user_roles'),
    ]

    operations = [
        migrations.RunPython(create_default_roles, reverse_create_default_roles),
    ]

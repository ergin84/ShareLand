from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_consolidate_author_profile_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('user', 'User'), ('author', 'Author'), ('researcher', 'Researcher'), ('contributor', 'Contributor'), ('admin', 'Administrator'), ('moderator', 'Moderator')], max_length=50, unique=True)),
                ('description', models.TextField(blank=True, help_text='Description of this role', null=True)),
                ('permissions', models.TextField(blank=True, help_text='Comma-separated list of permissions (for reference)', null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'user_role',
                'ordering': ['role'],
            },
        ),
        migrations.AddField(
            model_name='profile',
            name='user_roles',
            field=models.ManyToManyField(blank=True, help_text='Roles assigned to this user', related_name='profiles', to='users.userrole'),
        ),
    ]

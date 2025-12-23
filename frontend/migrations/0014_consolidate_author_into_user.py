from django.db import migrations, models
import django.db.models.deletion


def migrate_author_to_user_profile(apps, schema_editor):
    """
    Migrate Author table data to User/Profile.
    For each Author:
    - If linked to a User, update their Profile with author fields (or create profile if missing)
    - If not linked, create a new User with the author data
    Then update ResearchAuthor to point to the User instead of Author.
    """
    Author = apps.get_model('frontend', 'Author')
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('users', 'Profile')
    ResearchAuthor = apps.get_model('frontend', 'ResearchAuthor')
    
    for author in Author.objects.all():
        if author.user:
            # Author is already linked to a User; update/create their Profile
            profile, created = Profile.objects.get_or_create(user=author.user)
            # Migrate author fields to profile if they're missing
            if author.contact_email and not profile.contact_email:
                profile.contact_email = author.contact_email
            if author.id_anagraphic and not profile.id_anagraphic:
                profile.id_anagraphic = author.id_anagraphic
            # Only update name/surname if User's first/last_name are empty
            if not author.user.first_name and author.name:
                author.user.first_name = author.name
            if not author.user.last_name and author.surname:
                author.user.last_name = author.surname
            if author.affiliation and not profile.affiliation:
                profile.affiliation = author.affiliation
            if author.orcid and not profile.orcid:
                profile.orcid = author.orcid
            profile.save()
            author.user.save()
            
            # Update ResearchAuthor to point to this User instead of Author
            ResearchAuthor.objects.filter(id_author_id=author.id).update(id_author_id=author.user.id)
        else:
            # Author is not linked to a User; create one from author data
            # Use contact_email if available, else generate from name
            email = author.contact_email
            if not email:
                # Fallback: generate email from name if no contact_email
                name_part = (author.name or '').lower().replace(' ', '.')
                surname_part = (author.surname or '').lower().replace(' ', '.')
                if name_part and surname_part:
                    email = f'{name_part}.{surname_part}@shareland.local'
                elif name_part:
                    email = f'{name_part}@shareland.local'
                elif surname_part:
                    email = f'{surname_part}@shareland.local'
                else:
                    # Last resort: use author UUID as part of email
                    email = f'author.{str(author.id)[:8]}@shareland.local'
            
            # Generate unique username
            base_username = (author.name or '').lower().replace(' ', '.') or f'author_{str(author.id)[:8]}'
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_username}{counter}'
                counter += 1
            
            # Create User for this standalone Author
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=author.name or '',
                last_name=author.surname or '',
                is_active=False  # Inactive by default since they didn't register
            )
            
            # Create Profile for this new User
            profile = Profile.objects.create(
                user=user,
                affiliation=author.affiliation or '',
                orcid=author.orcid or '',
                contact_email=author.contact_email or '',
                id_anagraphic=author.id_anagraphic
            )
            
            # Update ResearchAuthor to point to this new User instead of Author
            ResearchAuthor.objects.filter(id_author_id=author.id).update(id_author_id=user.id)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_consolidate_author_profile_fields'),
        ('frontend', '0013_unique_site_research'),
    ]

    operations = [
        # Step 1: Add new integer FK column for User
        migrations.AddField(
            model_name='researchauthor',
            name='id_author_new',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='research_authorships', to='auth.user'),
        ),
        # Step 2: Migrate Author data to User/Profile and populate new FK
        migrations.RunPython(migrate_author_to_user_profile, migrations.RunPython.noop),
        # Step 3: Remove old UUID FK and rename new one
        migrations.RemoveField(
            model_name='researchauthor',
            name='id_author',
        ),
        migrations.RenameField(
            model_name='researchauthor',
            old_name='id_author_new',
            new_name='id_author',
        ),
    ]


from django.db import models
from django.contrib.auth.models import User
from PIL import Image


class UserRole(models.Model):
    """
    Role definitions for users (e.g., user, author, researcher, contributor, admin, moderator).
    Allows flexible role-based access control.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('author', 'Author'),
        ('researcher', 'Researcher'),
        ('contributor', 'Contributor'),
        ('admin', 'Administrator'),
        ('moderator', 'Moderator'),
    ]
    
    role = models.CharField(max_length=50, unique=True, choices=ROLE_CHOICES)
    description = models.TextField(blank=True, null=True, help_text='Description of this role')
    permissions = models.TextField(blank=True, null=True, help_text='Comma-separated list of permissions (for reference)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_role'
        ordering = ['role']
    
    def __str__(self):
        return f'{self.get_role_display()}'


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default='default.jpg', upload_to='profile_pics')
    birth_date = models.DateField(null=True, blank=True)
    qualification = models.CharField(max_length=100, null=True, blank=True)
    affiliation = models.CharField(max_length=200, blank=True, null=True)
    orcid = models.CharField(max_length=19, blank=True, null=True, unique=True, help_text='ORCID ID (e.g., 0000-0000-0000-0000)')
    contact_email = models.EmailField(blank=True, null=True, help_text='Alternative contact email for research/author purposes')
    id_anagraphic = models.IntegerField(blank=True, null=True, help_text='Legacy anagraphic ID from imported data')
    user_roles = models.ManyToManyField(UserRole, blank=True, related_name='profiles', help_text='Roles assigned to this user')

    def __str__(self):
        return f'{self.user.username} Profile'
    
    def get_full_name(self):
        """Get full name from User's first/last name, fallback to username"""
        full_name = self.user.get_full_name()
        if full_name:
            return full_name
        return self.user.username
    
    def get_display_name(self):
        """Get display name: full name if available, otherwise username"""
        full_name = self.get_full_name()
        if full_name and full_name != self.user.username:
            return full_name
        return self.user.username
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        return self.user_roles.filter(role=role_name).exists()
    
    def get_role_names(self):
        """Get list of role names for this user"""
        return list(self.user_roles.values_list('role', flat=True))

    def save(self, *args, **kwargs):
        super(Profile, self).save(*args, **kwargs)
        
        if self.image and hasattr(self.image, 'path'):
            try:
                img = Image.open(self.image.path)
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.image.path)
            except Exception:
                # Silently fail if image processing fails (e.g., file doesn't exist)
                pass

from django.db import models
from django.contrib.auth.models import User
from PIL import Image


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default='default.jpg', upload_to='profile_pics')
    birth_date = models.DateField(null=True, blank=True)
    qualification = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=100, blank=True)
    surname = models.CharField(max_length=100, blank=True)
    affiliation = models.CharField(max_length=200, blank=True, null=True)
    orcid = models.CharField(max_length=19, blank=True, null=True, help_text='ORCID ID (e.g., 0000-0000-0000-0000)')

    def __str__(self):
        return f'{self.user.username} Profile'
    
    def get_full_name(self):
        """Get full name from profile, fallback to User's get_full_name()"""
        if self.name and self.surname:
            return f'{self.name} {self.surname}'.strip()
        elif self.name:
            return self.name
        elif self.surname:
            return self.surname
        # Fallback to User's first_name/last_name or username
        return self.user.get_full_name() or self.user.username
    
    def get_display_name(self):
        """Get display name: full name if available, otherwise username"""
        full_name = self.get_full_name()
        if full_name and full_name != self.user.username:
            return full_name
        return self.user.username

    def save(self, *args, **kwargs):
        super(Profile, self).save(*args, **kwargs)

        img = Image.open(self.image.path)

        if img.height > 300 or img.width > 300:
            output_size = (300, 300)
            img.thumbnail(output_size)
            img.save(self.image.path)

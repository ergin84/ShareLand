from django.contrib import admin
from django.contrib.auth.models import User

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'surname', 'affiliation', 'orcid']
    list_filter = ['affiliation']
    search_fields = ['user__username', 'name', 'surname', 'affiliation', 'orcid']
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Personal Information', {'fields': ('name', 'surname', 'birth_date', 'qualification')}),
        ('Professional Information', {'fields': ('affiliation', 'orcid')}),
        ('Profile Image', {'fields': ('image',)}),
    )


# python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ShareLand.settings')
django.setup()

from frontend.models import SiteInvestigation

for obj in SiteInvestigation.objects.filter(id_site=124):
    print(f"id: {obj.id}, id_site: {obj.id_site}, id_investigation: {obj.id_investigation}")
from django.db import migrations, models
from django.db.models import Count


def dedupe_site_research(apps, schema_editor):
    SiteResearch = apps.get_model('frontend', 'SiteResearch')

    dup_groups = (
        SiteResearch.objects
        .values('id_site_id', 'id_research_id')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )

    for grp in dup_groups:
        qs = SiteResearch.objects.filter(
            id_site_id=grp['id_site_id'],
            id_research_id=grp['id_research_id']
        ).order_by('id')
        ids = list(qs.values_list('id', flat=True))
        if len(ids) > 1:
            SiteResearch.objects.filter(id__in=ids[1:]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('frontend', '0012_unique_research_author'),
    ]

    operations = [
        migrations.RunPython(dedupe_site_research, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='siteresearch',
            constraint=models.UniqueConstraint(
                fields=['id_site', 'id_research'],
                name='unique_site_research_pair'
            ),
        ),
    ]

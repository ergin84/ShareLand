from django.db import migrations, models
from django.db.models import Count


def dedupe_research_author(apps, schema_editor):
    ResearchAuthor = apps.get_model('frontend', 'ResearchAuthor')

    # Find duplicate (id_research, id_author) pairs
    dup_groups = (
        ResearchAuthor.objects
        .values('id_research_id', 'id_author_id')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )

    for grp in dup_groups:
        qs = ResearchAuthor.objects.filter(
            id_research_id=grp['id_research_id'],
            id_author_id=grp['id_author_id']
        ).order_by('id')
        # Keep the first row, delete the rest
        ids = list(qs.values_list('id', flat=True))
        if len(ids) > 1:
            ResearchAuthor.objects.filter(id__in=ids[1:]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('frontend', '0011_add_archaeological_evidence_to_image'),
    ]

    operations = [
        migrations.RunPython(dedupe_research_author, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='researchauthor',
            constraint=models.UniqueConstraint(
                fields=['id_research', 'id_author'],
                name='unique_research_author_pair'
            ),
        ),
    ]

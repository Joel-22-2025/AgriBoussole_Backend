"""Complète les régions manquantes des villes de référence.

L’import initial a créé certaines villes sans région : le formulaire
d’accréditation ne pouvait donc pas les proposer dans la cascade
pays → département → ville.
"""

from django.db import migrations

REGIONS_PAR_VILLE = {
    'Ouidah': 'Atlantique',
    'Porto-Novo': 'Ouémé',
    'Bohicon': 'Zou',
    'Natitingou': 'Atacora',
    'Akpro-Missérété': 'Ouémé',
    'Godomey': 'Atlantique',
    'Abidjan': 'Abidjan',
    'Yamoussoukro': 'Yamoussoukro',
}


def fill_regions(apps, schema_editor):
    Ville = apps.get_model('structures', 'Ville')
    for nom, region in REGIONS_PAR_VILLE.items():
        Ville.objects.filter(nom__iexact=nom, region='').update(region=region)


def clear_regions(apps, schema_editor):
    Ville = apps.get_model('structures', 'Ville')
    for nom, region in REGIONS_PAR_VILLE.items():
        Ville.objects.filter(nom__iexact=nom, region=region).update(region='')


class Migration(migrations.Migration):
    dependencies = [
        ('structures', '0004_structure_logo'),
    ]

    operations = [
        migrations.RunPython(fill_regions, clear_regions),
    ]

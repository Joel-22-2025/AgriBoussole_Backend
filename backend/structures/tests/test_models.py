"""Tests pour structures : modèle, API publique et protection des contacts."""

import pytest
from rest_framework.test import APIClient

from structures.models import Structure, Ville
from structures.serializers import StructurePublicSerializer


@pytest.mark.django_db
def test_structure_creation():
    structure = Structure.objects.create(
        nom='Incubateur Test',
        pays='BJ',
        region_departement='Littoral',
        acronyme='IT',
        est_incubateur=True,
        est_publiee=True,
    )
    assert str(structure) == 'Incubateur Test'
    assert Structure.objects.filter(pays='BJ').count() == 1


@pytest.mark.django_db
def test_public_serializer_hides_contact_fields():
    structure = Structure.objects.create(
        nom='Structure Contact',
        pays='SN',
        contact_nom='Secret',
        contact_fonction='Directeur',
        contact_email='secret@example.com',
        contact_telephone='+221700000000',
        est_publiee=True,
    )
    data = StructurePublicSerializer(structure).data
    assert 'contact_nom' not in data
    assert 'contact_email' not in data
    assert 'contact_telephone' not in data


@pytest.mark.django_db
def test_public_list_and_detail():
    structure = Structure.objects.create(nom='Publique', pays='CI', est_publiee=True)
    client = APIClient()

    listing = client.get('/api/structures/')
    assert listing.status_code == 200

    detail = client.get(f'/api/structures/{structure.id}/')
    assert detail.status_code == 200
    assert detail.json()['nom'] == 'Publique'


@pytest.mark.django_db
def test_ville_creation_and_link():
    ville = Ville.objects.create(nom='Cotonou', region='Littoral')
    structure = Structure.objects.create(nom='Avec ville', pays='BJ', ville_siege=ville)
    assert structure.ville_siege == ville

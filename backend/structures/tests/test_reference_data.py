"""Tests des données de référence utilisées par le formulaire SAEI."""

import pytest
from rest_framework.test import APIClient

from structures.models import Structure, Ville


@pytest.fixture
def reference_data(db):
    cotonou = Ville.objects.create(nom='Cotonou', region='Littoral')
    dakar = Ville.objects.create(nom='Dakar', region='Dakar')
    Structure.objects.create(
        nom='Structure Bénin',
        pays='BJ',
        ville_siege=cotonou,
        public_cible='Jeunes; Femmes',
        est_publiee=True,
    )
    Structure.objects.create(
        nom='Structure Sénégal',
        pays='SN',
        ville_siege=dakar,
        public_cible='Femmes; Startups',
        est_publiee=True,
    )
    return APIClient()


def _noms_villes(response):
    payload = response.json()
    items = payload['results'] if isinstance(payload, dict) else payload
    return [item['nom'] for item in items]


@pytest.mark.django_db
def test_villes_are_filtered_by_pays(reference_data):
    response = reference_data.get('/api/villes/', {'pays': 'BJ'})
    assert response.status_code == 200
    assert _noms_villes(response) == ['Cotonou']


@pytest.mark.django_db
def test_villes_are_filtered_by_region(reference_data):
    response = reference_data.get('/api/villes/', {'pays': 'SN', 'region': 'Dakar'})
    assert response.status_code == 200
    assert _noms_villes(response) == ['Dakar']


@pytest.mark.django_db
def test_publics_cibles_are_distinct_and_sorted(reference_data):
    response = reference_data.get('/api/publics-cibles/')
    assert response.status_code == 200
    assert response.json() == ['Femmes', 'Jeunes', 'Startups']

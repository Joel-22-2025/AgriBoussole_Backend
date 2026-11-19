"""Tests des filtres combinés de l'annuaire public."""

import pytest
from rest_framework.test import APIClient

from structures.models import Structure, Ville


@pytest.fixture
def annuaire(db):
    cotonou = Ville.objects.create(nom='Cotonou', region='Littoral')
    dakar = Ville.objects.create(nom='Dakar', region='Dakar')

    Structure.objects.create(
        nom='AgriTech Bénin',
        pays='BJ',
        ville_siege=cotonou,
        typologie='Incubateur | Appui technique',
        public_cible='Jeunes entrepreneurs',
        stade='Incubation',
        service='Accélération agricole',
        est_publiee=True,
    )
    Structure.objects.create(
        nom='Réseau Femmes Sénégal',
        pays='SN',
        ville_siege=dakar,
        typologie='Plateforme réseau',
        public_cible='Femmes',
        stade='Développement',
        service='Mise en réseau',
        est_publiee=True,
    )
    Structure.objects.create(
        nom='Incubateur Côte d’Ivoire',
        pays='CI',
        typologie='Incubateur',
        public_cible='Startups',
        stade='Idéation',
        est_publiee=True,
    )
    Structure.objects.create(
        nom='Structure Non Publiée',
        pays='BJ',
        ville_siege=cotonou,
        est_publiee=False,
    )
    return APIClient()


def _noms(response):
    return [item['nom'] for item in response.json()['results']]


@pytest.mark.django_db
def test_search_matches_name_city_and_service(annuaire):
    assert _noms(annuaire.get('/api/structures/', {'search': 'agritech'})) == ['AgriTech Bénin']
    assert _noms(annuaire.get('/api/structures/', {'search': 'cotonou'})) == ['AgriTech Bénin']
    assert _noms(annuaire.get('/api/structures/', {'search': 'mise en réseau'})) == [
        'Réseau Femmes Sénégal'
    ]


@pytest.mark.django_db
def test_pays_accepts_code_or_label(annuaire):
    by_code = annuaire.get('/api/structures/', {'pays': 'SN'})
    by_label = annuaire.get('/api/structures/', {'Pays': 'Sénégal'})

    assert _noms(by_code) == ['Réseau Femmes Sénégal']
    assert _noms(by_label) == ['Réseau Femmes Sénégal']


@pytest.mark.django_db
def test_combined_filters_are_cumulative(annuaire):
    response = annuaire.get(
        '/api/structures/',
        {
            'pays': 'BJ',
            'ville': 'coton',
            'typologie': 'incubateur',
            'cible': 'jeunes',
            'stade': 'incubation',
        },
    )

    assert _noms(response) == ['AgriTech Bénin']


@pytest.mark.django_db
def test_unpublished_never_appears(annuaire):
    response = annuaire.get('/api/structures/', {'search': 'non publiée'})

    assert response.status_code == 200
    assert response.json()['count'] == 0

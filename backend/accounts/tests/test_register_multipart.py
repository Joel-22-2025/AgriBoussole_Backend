"""Test du formulaire SAEI tel qu’envoyé par le frontend (multipart)."""

import pytest

from accounts.models import User


@pytest.mark.django_db
def test_register_saei_multipart_without_site_web(client):
    payload = {
        'email': 'multipart.saei@test.bj',
        'password': 'MonMotDePasse123!',
        'nom_structure': 'Structure Multipart',
        'pays': 'BJ',
        'ville': 'Porto-Novo',
        'region_departement': 'Ouémé',
        'zone_intervention': 'Sud-Bénin',
        'acronyme': 'SM',
        'statut_juridique': 'Association',
        'est_incubateur': 'true',
        'est_accelerateur': 'false',
        'service': 'Accompagnement',
        'public_cible': 'Jeunes; Femmes',
        'stade': 'Idéation',
        'contact_nom': 'Koffi Ahou',
        'contact_fonction': 'Directeur',
        'contact_email': 'contact@multipart.bj',
        'contact_telephone': '+22990000000',
        'telephone_structure': '+22990000000',
    }
    response = client.post('/api/auth/register/saei/', payload, format='multipart')
    assert response.status_code == 201, response.content
    user = User.objects.get(email='multipart.saei@test.bj')
    assert user.saei_profile.structure.site_web in (None, '')
    assert user.saei_profile.structure.public_cible == 'Jeunes; Femmes'

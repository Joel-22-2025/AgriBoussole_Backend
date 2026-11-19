"""Tests du quiz d’identification de phase des entrepreneurs."""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import EntrepreneurProfile, Role, Status, User
from accounts.phase import MAX_SCORE
from structures.models import Structure, Ville


@pytest.fixture
def client():
    return APIClient()


def _login(client, role=Role.ENTREPRENEUR, with_profile=True):
    user = User.objects.create_user(
        email=f'{role.lower()}@test.bj',
        password='TestPass123!',
        role=role,
        status=Status.APPROVED,
    )
    if with_profile:
        EntrepreneurProfile.objects.create(
            user=user,
            pays='BJ',
            ville='Cotonou',
            type_profil='individuel',
        )
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return user


def _answers(choice):
    return {f'q{index}': choice for index in range(1, 8)}


@pytest.mark.django_db
def test_phase_get_before_quiz(client):
    _login(client)

    response = client.get('/api/auth/entrepreneurs/phase/')

    assert response.status_code == 200
    body = response.json()
    assert body['phase'] is None
    assert body['score'] is None
    assert body['max_score'] == MAX_SCORE


@pytest.mark.django_db
def test_phase_minimum_score_gives_ideation(client):
    _login(client)

    response = client.post(
        '/api/auth/entrepreneurs/phase/',
        {'answers': _answers('A')},
        format='json',
    )

    assert response.status_code == 200, response.content
    body = response.json()
    assert body['score'] == 0
    assert body['phase'] == 'IDEATION'
    assert body['label'] == 'Idéation'
    assert body['stade'] == 'Idéation'
    assert body['completed_at'] is not None
    assert body['profile']['phase'] == 'IDEATION'


@pytest.mark.django_db
def test_phase_maximum_score_gives_passage_a_lechelle(client):
    _login(client)

    response = client.post(
        '/api/auth/entrepreneurs/phase/',
        {'answers': _answers('D')},
        format='json',
    )

    assert response.status_code == 200, response.content
    body = response.json()
    assert body['score'] == 21
    assert body['phase'] == 'PASSAGE_ECHELLE'
    assert body['label'] == 'Passage à l’échelle'
    assert body['range'] == '20 – 21'


@pytest.mark.django_db
def test_phase_result_is_persisted_and_returned_by_me(client):
    user = _login(client)
    client.post(
        '/api/auth/entrepreneurs/phase/',
        {'answers': _answers('C')},
        format='json',
    )

    me = client.get('/api/auth/me/').json()
    assert me['profile']['score_phase'] == 14
    assert me['profile']['phase'] == 'ACCELERATION'

    get = client.get('/api/auth/entrepreneurs/phase/').json()
    assert get['score'] == 14
    assert get['answers'] == _answers('C')

    user.refresh_from_db()
    assert user.entrepreneur_profile.score_phase == 14


@pytest.mark.django_db
def test_phase_rejects_incomplete_or_invalid_answers(client):
    _login(client)

    incomplete = client.post(
        '/api/auth/entrepreneurs/phase/',
        {'answers': {'q1': 'A'}},
        format='json',
    )
    invalid = client.post(
        '/api/auth/entrepreneurs/phase/',
        {'answers': {**_answers('A'), 'q7': 'E'}},
        format='json',
    )

    assert incomplete.status_code == 400
    assert invalid.status_code == 400


@pytest.mark.django_db
def test_phase_is_forbidden_for_non_entrepreneurs(client):
    _login(client, role=Role.ADMIN, with_profile=False)

    response = client.get('/api/auth/entrepreneurs/phase/')

    assert response.status_code == 403


@pytest.mark.django_db
def test_recommandations_require_completed_quiz(client):
    _login(client)

    response = client.get('/api/auth/entrepreneurs/phase/recommandations/')

    assert response.status_code == 400
    assert 'quiz' in response.json()['message'].lower()


@pytest.mark.django_db
def test_recommandations_use_pays_ville_and_phase(client):
    _login(client)
    cotonou = Ville.objects.create(nom='Cotonou')
    Structure.objects.create(
        nom='Incubateur Cotonou',
        pays='BJ',
        ville_siege=cotonou,
        stade='Incubation',
        score_pertinence=4,
    )
    Structure.objects.create(
        nom='Structure Parakou',
        pays='BJ',
        stade='Incubation',
    )
    Structure.objects.create(
        nom='Structure Dakar',
        pays='SN',
        stade='Incubation',
    )
    Structure.objects.create(
        nom='Structure Masquee',
        pays='BJ',
        ville_siege=cotonou,
        stade='Incubation',
        est_publiee=False,
    )

    client.post(
        '/api/auth/entrepreneurs/phase/',
        {'answers': _answers('B')},
        format='json',
    )
    response = client.get('/api/auth/entrepreneurs/phase/recommandations/')

    assert response.status_code == 200, response.content
    body = response.json()
    assert body['pays'] == 'BJ'
    assert body['ville'] == 'Cotonou'
    assert body['stade'] == 'Incubation'
    assert body['fallback_all_pays'] is False
    assert body['count'] == 2
    assert [item['nom'] for item in body['results']] == [
        'Incubateur Cotonou',
        'Structure Parakou',
    ]
    assert 'Même ville' in body['results'][0]['match_reasons']
    assert 'Phase compatible' in body['results'][0]['match_reasons']
    assert body['results'][0]['match_score'] > body['results'][1]['match_score']


@pytest.mark.django_db
def test_recommandations_fallback_to_all_pays_when_pays_empty(client):
    _login(client)
    Structure.objects.create(nom='Structure Dakar', pays='SN', stade='Incubation')

    client.post(
        '/api/auth/entrepreneurs/phase/',
        {'answers': _answers('B')},
        format='json',
    )
    response = client.get('/api/auth/entrepreneurs/phase/recommandations/')

    assert response.status_code == 200
    body = response.json()
    assert body['fallback_all_pays'] is True
    assert body['count'] == 1
    assert 'Même pays' not in body['results'][0]['match_reasons']

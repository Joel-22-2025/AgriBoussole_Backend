"""Tests pour accounts (inscriptions, connexion, admin, logout)."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, Role, Status, SaeiProfile


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def entrepreneur(db):
    return User.objects.create_user(
        email='entrepreneur@test.bj',
        password='EntrepreneurPass123!',
        role=Role.ENTREPRENEUR,
        status=Status.APPROVED,
    )


@pytest.fixture
def saei_pending(db):
    return User.objects.create_user(
        email='saei.pending@test.bj',
        password='SaeiPass123!',
        role=Role.SAEI,
        status=Status.PENDING,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email='admin@test.bj',
        password='AdminPass123!',
        role=Role.ADMIN,
        status=Status.APPROVED,
        is_staff=True,
    )


def auth(client, user):
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.mark.django_db
def test_register_entrepreneur(client):
    payload = {
        'email': 'new.entrepreneur@test.bj',
        'password': 'MonMotDePasse123!',
        'first_name': 'Awa',
        'last_name': 'Doe',
        'pays': 'BJ',
        'ville': 'Cotonou',
        'type_profil': 'individuel',
        'est_femme': True,
        'est_jeune': True,
        'filiere': 'Agroalimentaire',
    }
    resp = client.post('/api/auth/register/entrepreneur/', payload, format='json')
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert 'access' in body and 'refresh' in body
    assert User.objects.filter(email='new.entrepreneur@test.bj').exists()


@pytest.mark.django_db
def test_register_saei_pending_without_token(client):
    payload = {
        'email': 'new.saei@test.bj',
        'password': 'MonMotDePasse123!',
        'first_name': 'Koffi',
        'last_name': 'Ahou',
        'nom_structure': 'Incubateur Agricole',
        'pays': 'BJ',
        'ville': 'Porto-Novo',
        'region_departement': 'Ouémé',
        'zone_intervention': 'Sud-Bénin',
        'acronyme': 'IA',
        'statut_juridique': 'Association',
        'est_incubateur': True,
        'service': 'Accompagnement',
        'public_cible': 'Jeunes agriculteurs',
        'stade': 'Idéation',
        'contact_nom': 'Koffi Ahou',
        'contact_fonction': 'Directeur',
        'contact_email': 'contact@incubateur.bj',
        'contact_telephone': '+22990000000',
        'telephone_structure': '+22990000000',
        'message': 'Demande de test',
    }
    resp = client.post('/api/auth/register/saei/', payload, format='json')
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert 'access' not in body
    assert body['status'] == 'PENDING'

    from structures.models import Structure
    structure = Structure.objects.get(nom='Incubateur Agricole')
    assert structure.est_publiee is False
    assert structure.est_incubateur is True
    assert structure.statut_juridique == 'Association'


@pytest.mark.django_db
def test_login_saei_pending_refused(client, saei_pending):
    resp = client.post(
        '/api/auth/login/',
        {'email': saei_pending.email, 'password': 'SaeiPass123!'},
        format='json',
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body.get('status') == 'PENDING'


@pytest.mark.django_db
def test_login_saei_approved_accepted(client, saei_pending):
    saei_pending.status = Status.APPROVED
    saei_pending.save()
    resp = client.post(
        '/api/auth/login/',
        {'email': saei_pending.email, 'password': 'SaeiPass123!'},
        format='json',
    )
    assert resp.status_code == 200
    assert 'access' in resp.json()


@pytest.mark.django_db
def test_entrepreneur_cannot_access_admin(client, entrepreneur):
    auth(client, entrepreneur)
    resp = client.get('/api/admin/users/')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_can_list_users(client, admin_user):
    auth(client, admin_user)
    resp = client.get('/api/admin/users/')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_logout_blacklists_refresh_token(client, entrepreneur):
    login = client.post(
        '/api/auth/login/',
        {'email': entrepreneur.email, 'password': 'EntrepreneurPass123!'},
        format='json',
    )
    assert login.status_code == 200
    refresh = login.json()['refresh']

    auth(client, entrepreneur)
    logout = client.post('/api/auth/logout/', {'refresh': refresh}, format='json')
    assert logout.status_code in (200, 204, 205)

    client.credentials()
    replay = client.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')
    assert replay.status_code == 401


@pytest.mark.django_db
def test_admin_creates_admin(client, db):
    admin = User.objects.create_superuser(
        email='admin.createur@test.bj', password='AdminPass123!'
    )
    auth(client, admin)
    resp = client.post(
        '/api/admin/admins/',
        {
            'email': 'new.admin@test.bj',
            'password': 'AdminPass123!',
            'first_name': 'Admin',
            'last_name': 'Test',
        },
        format='json',
    )
    assert resp.status_code == 201, resp.content
    assert User.objects.filter(email='new.admin@test.bj', role=Role.ADMIN).exists()


def saei_payload(email='candidate.saei@test.bj'):
    return {
        'email': email,
        'password': 'MonMotDePasse123!',
        'first_name': 'Koffi',
        'last_name': 'Ahou',
        'nom_structure': 'Incubateur Agricole',
        'pays': 'BJ',
        'ville': 'Porto-Novo',
        'region_departement': 'Ouémé',
        'zone_intervention': 'Sud-Bénin',
        'acronyme': 'IA',
        'statut_juridique': 'Association',
        'est_incubateur': True,
        'service': 'Accompagnement',
        'public_cible': 'Jeunes agriculteurs',
        'stade': 'Idéation',
        'contact_nom': 'Koffi Ahou',
        'contact_fonction': 'Directeur',
        'contact_email': 'contact@incubateur.bj',
        'contact_telephone': '+22990000000',
        'telephone_structure': '+22990000000',
    }


@pytest.mark.django_db
def test_admin_approves_saei_and_structure_is_published(client, admin_user):
    register = client.post('/api/auth/register/saei/', saei_payload(), format='json')
    assert register.status_code == 201, register.content

    profile = SaeiProfile.objects.get(user__email='candidate.saei@test.bj')
    assert profile.structure is not None
    assert profile.structure.est_publiee is False

    auth(client, admin_user)
    listing = client.get('/api/admin/saei-requests/?status=PENDING')
    assert listing.status_code == 200
    item = next(
        row for row in listing.json()['results']
        if row['email'] == 'candidate.saei@test.bj'
    )
    # L'id exposé doit être celui utilisé par /approve/ (id du SaeiProfile).
    assert item['id'] == profile.id
    assert item['structure']['nom'] == 'Incubateur Agricole'

    approve = client.post(f"/api/admin/saei-requests/{item['id']}/approve/", {}, format='json')
    assert approve.status_code == 200, approve.content

    profile.refresh_from_db()
    profile.structure.refresh_from_db()
    assert profile.user.status == Status.APPROVED
    assert profile.structure.est_publiee is True

    client.credentials()
    login = client.post(
        '/api/auth/login/',
        {'email': 'candidate.saei@test.bj', 'password': 'MonMotDePasse123!'},
        format='json',
    )
    assert login.status_code == 200, login.content


@pytest.mark.django_db
def test_saei_registration_rejects_missing_typology(client):
    payload = saei_payload('no.type@test.bj')
    for field in (
        'est_incubateur', 'est_accelerateur', 'est_recherche_innovation',
        'est_appui_technique', 'est_structure_financement',
        'est_plateforme_reseau',
    ):
        payload.pop(field, None)
    resp = client.post('/api/auth/register/saei/', payload, format='json')
    assert resp.status_code == 400

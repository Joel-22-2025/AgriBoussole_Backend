"""Tests des parcours SAEI ↔ entrepreneur (offres, indicateurs, messagerie, équipe)."""

import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import EntrepreneurProfile, Role, SaeiProfile, Status, User
from engagement.models import Candidature, Conversation, EvaluationEquipe, Message, Tache
from structures.models import Structure


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def saei(db):
    user = User.objects.create_user(
        email='saei.flow@test.bj',
        password='SaeiFlow123!',
        first_name='Awa',
        role=Role.SAEI,
        status=Status.APPROVED,
    )
    structure = Structure.objects.create(
        nom='Incubateur Test',
        pays='BJ',
        contact_email='contact.flow@test.bj',
        email_structure='structure.flow@test.bj',
    )
    profile = SaeiProfile.objects.create(
        user=user,
        structure=structure,
        nom_structure_demandee='Incubateur Test',
        pays='BJ',
        ville='Cotonou',
        telephone_structure='+22901000000',
    )
    return user, profile, structure


@pytest.fixture
def entrepreneur(db):
    user = User.objects.create_user(
        email='entrepreneur.flow@test.bj',
        password='EntrepreneurFlow123!',
        first_name='Koffi',
        role=Role.ENTREPRENEUR,
        status=Status.APPROVED,
    )
    profile = EntrepreneurProfile.objects.create(
        user=user,
        pays='BJ',
        ville='Cotonou',
        type_profil='startup',
        phase='CREATION',
        score_phase=7,
    )
    return user, profile


def auth(client, user):
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
@pytest.mark.django_db
def test_offre_et_candidature_avec_emails(api, saei, entrepreneur):
    saei_user, saei_profile, _ = saei
    entrepreneur_user, _ = entrepreneur
    mail.outbox = []

    auth(api, saei_user)
    response = api.post(
        '/api/engagement/offres/',
        {
            'titre': 'Programme incubation agri',
            'programme': 'Incubation agri',
            'description': 'Accompagnement de 6 mois.',
            'conditions_eligibilite': 'Avoir un projet agricole au Bénin.',
            'type_offre': 'Incubation',
            'statut': 'PUBLIEE',
        },
        format='json',
    )
    assert response.status_code == 201, response.content
    offre_id = response.data['id']

    auth(api, entrepreneur_user)
    listing = api.get('/api/engagement/offres/')
    assert listing.status_code == 200
    assert any(item['id'] == offre_id for item in listing.data['results'])

    candidature = api.post(
        '/api/engagement/candidatures/',
        {'offre_id': offre_id, 'message': 'Mon projet est une ferme maraîchère.'},
        format='json',
    )
    assert candidature.status_code == 201, candidature.content
    assert Candidature.objects.filter(offre_id=offre_id).count() == 1
    assert len(mail.outbox) == 2
    assert any('nouvelle candidature' in subject.lower() for subject in [m.subject for m in mail.outbox])


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
@pytest.mark.django_db
def test_notification_contact_et_chat(api, saei, entrepreneur):
    saei_user, _, structure = saei
    entrepreneur_user, entrepreneur_profile = entrepreneur
    mail.outbox = []

    auth(api, saei_user)
    notification = api.post(
        '/api/engagement/saei/notifier/',
        {'entrepreneur_id': entrepreneur_profile.id, 'content': 'Votre dossier est prêt.'},
        format='json',
    )
    assert notification.status_code == 201, notification.content
    assert notification.data['type_message'] == 'NOTIFICATION'

    auth(api, entrepreneur_user)
    unread = api.get('/api/engagement/notifications/?unread=true')
    assert unread.status_code == 200
    assert unread.data['count'] == 1

    mail.outbox = []
    contact = api.post(
        '/api/engagement/contact-saei/',
        {
            'structure_id': structure.id,
            'programme': 'Accélération agri',
            'message': 'Je souhaite intégrer ce programme.',
        },
        format='json',
    )
    assert contact.status_code == 201, contact.content
    conversation_id = contact.data['conversation']
    assert Message.objects.get(pk=contact.data['id']).type_message == 'DEMANDE_INSERTION'
    assert len(mail.outbox) == 2

    chat = api.post(
        f'/api/engagement/conversations/{conversation_id}/messages/',
        {'content': 'Bonjour, merci pour votre retour.'},
        format='json',
    )
    assert chat.status_code == 201, chat.content
    assert chat.data['type_message'] == 'CHAT'

    messages = api.get(f'/api/engagement/conversations/{conversation_id}/messages/')
    assert messages.status_code == 200
    assert messages.data['count'] >= 2
    assert Conversation.objects.filter(pk=conversation_id).exists()


@pytest.mark.django_db
def test_indicateur_likes_et_commentaires(api, saei, entrepreneur):
    saei_user, _, _ = saei
    entrepreneur_user, _ = entrepreneur

    auth(api, saei_user)
    indicateur = api.post(
        '/api/engagement/indicateurs/',
        {
            'titre': 'Taux d’insertion',
            'contenu': '82 % des accompagnés ont été insérés en 2026.',
            'type_media': 'TEXTE',
        },
        format='json',
    )
    assert indicateur.status_code == 201, indicateur.content
    indicateur_id = indicateur.data['id']

    auth(api, entrepreneur_user)
    like = api.post(f'/api/engagement/indicateurs/{indicateur_id}/like/')
    assert like.status_code == 200
    assert like.data == {'liked': True, 'likes_count': 1}
    unlike = api.post(f'/api/engagement/indicateurs/{indicateur_id}/like/')
    assert unlike.data == {'liked': False, 'likes_count': 0}

    commentaire = api.post(
        f'/api/engagement/indicateurs/{indicateur_id}/commentaires/',
        {'contenu': 'Bravo pour ce résultat !'},
        format='json',
    )
    assert commentaire.status_code == 201, commentaire.content

    listing = api.get('/api/engagement/indicateurs/')
    assert listing.status_code == 200
    assert listing.data['results'][0]['likes_count'] == 0
    assert len(listing.data['results'][0]['commentaires']) == 1


@pytest.mark.django_db
def test_equipe_tache_et_evaluation(api, saei, entrepreneur):
    saei_user, saei_profile, _ = saei
    entrepreneur_user, entrepreneur_profile = entrepreneur

    auth(api, saei_user)
    membre = api.post(
        '/api/engagement/equipe/',
        {'entrepreneur_id': entrepreneur_profile.id, 'role': 'Chargé de projet'},
        format='json',
    )
    assert membre.status_code == 201, membre.content

    tache = api.post(
        '/api/engagement/taches/',
        {
            'membre': membre.data['id'],
            'titre': 'Suivi des indicateurs',
            'description': 'Mettre à jour le tableau de bord.',
            'type_tache': 'TACHE',
        },
        format='json',
    )
    assert tache.status_code == 201, tache.content

    auth(api, entrepreneur_user)
    statut = api.patch(
        f"/api/engagement/taches/{tache.data['id']}/statut/", {'statut': 'TERMINEE'}, format='json'
    )
    assert statut.status_code == 200
    assert Tache.objects.get(pk=tache.data['id']).statut == 'TERMINEE'

    evaluation = api.post(
        '/api/engagement/evaluations/',
        {'saei_id': saei_profile.id, 'note': 5, 'commentaire': 'Équipe très disponible.'},
        format='json',
    )
    assert evaluation.status_code == 201, evaluation.content
    assert EvaluationEquipe.objects.get().note == 5

    auth(api, saei_user)
    dashboard = api.get('/api/engagement/saei/dashboard/')
    assert dashboard.status_code == 200
    assert dashboard.data['note_moyenne'] == 5.0
    assert dashboard.data['entrepreneurs'] == 1

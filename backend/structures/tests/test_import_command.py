import pytest
from django.core.management import call_command

from accounts.models import Role, SaeiProfile, Status, User
from structures.models import Pays, Structure, Ville

pytestmark = pytest.mark.django_db


def _write_workbook(path):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'SAEI'
    sheet.append([
        'id', 'pays', 'ville', 'region_departement', 'nom_structure',
        'services', 'publics_cibles', 'stades_intervention', 'besoins_non_couverts',
        'profil_specialisation', 'est_incubateur', 'est_accelerateur',
        'telephone_structure', 'contact_nom', 'contact_email', 'email_structure',
        'site_web', 'score_iih', 'niveau_donnees', 'description',
        'latitude', 'longitude', 'acronyme', 'statut_juridique',
    ])
    sheet.append([
        'BJ-001', 'Bénin', 'Cotonou; Parakou', 'Atlantique', 'Structure test',
        'Formation; Coaching', 'Jeunes; Femmes', 'Idéation; Création',
        'Accès au financement', 'Spécialiste', 1, 0, '+229 0100000000',
        'Jean Dupont', 'jean@example.org', 'contact@example.org', 'www.example.org',
        85, 'Enquêtée (fiche complète)', 'Description de test',
        6.1319, 2.3889, 'ST', 'ONG',
    ])
    workbook.save(path)


def test_import_creates_structures_users_and_profiles(tmp_path):
    xlsx = tmp_path / 'saei.xlsx'
    _write_workbook(xlsx)

    call_command(
        'import_saei_from_xlsx',
        '--file', str(xlsx),
        '--email-domain', 'fixture.test',
    )

    structure = Structure.objects.get(nom='Structure test')
    assert structure.pays == Pays.BENIN
    assert structure.ville_siege.nom == 'Cotonou'
    assert structure.service == 'Formation; Coaching'
    assert structure.est_incubateur is True
    assert structure.est_accelerateur is False
    assert structure.specialisation == 'specialiste'
    assert structure.source == 'enquetee'
    assert structure.site_web == 'https://www.example.org'
    assert structure.score_pertinence == 85
    assert Ville.objects.filter(nom='Cotonou').count() == 1

    user = User.objects.get(email='saei001@fixture.test')
    assert user.role == Role.SAEI
    assert user.status == Status.APPROVED
    assert user.is_active is True
    assert user.check_password('Saei@2026')

    profile = SaeiProfile.objects.get(user=user)
    assert profile.structure == structure
    assert profile.nom_structure_demandee == 'Structure test'
    assert profile.ville == 'Cotonou'


def test_import_is_idempotent(tmp_path):
    xlsx = tmp_path / 'saei.xlsx'
    _write_workbook(xlsx)
    args = ['--file', str(xlsx), '--email-domain', 'fixture.test']

    call_command('import_saei_from_xlsx', *args)
    call_command('import_saei_from_xlsx', *args)

    assert Structure.objects.count() == 1
    assert User.objects.filter(role=Role.SAEI).count() == 1
    assert SaeiProfile.objects.count() == 1
    assert Ville.objects.count() == 1

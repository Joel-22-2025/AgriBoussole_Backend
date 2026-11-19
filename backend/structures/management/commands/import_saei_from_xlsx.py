"""Importe les structures SAEI du fichier XLSX unifié et crée un compte par structure.

La commande est idempotente : relancer l'import met à jour les structures,
les comptes et les profils existants sans créer de doublon.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import re
import unicodedata

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, SaeiProfile, Status, User
from structures.models import Pays, Structure, Ville

DEFAULT_XLSX = (
    Path(settings.BASE_DIR)
    / 'data'
    / 'SAEI_Benin_Senegal_CoteIvoire_base_unifiee.xlsx'
)

PAYS_MAP = {
    'benin': Pays.BENIN,
    'bj': Pays.BENIN,
    'senegal': Pays.SENEGAL,
    'sn': Pays.SENEGAL,
    'cote d ivoire': Pays.COTE_DIVOIRE,
    'cote divoire': Pays.COTE_DIVOIRE,
    'ci': Pays.COTE_DIVOIRE,
}

TRUE_VALUES = {'1', 'oui', 'yes', 'true', 'vrai'}
URL_RE = re.compile(r'^(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?$', re.I)


def as_text(value):
    """Normalise une cellule Excel en chaîne (les nombres entiers perdent leur .0)."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize(value):
    """Minuscules, sans accents ni ponctuation : sert aux comparaisons."""
    ascii_text = (
        unicodedata.normalize('NFKD', as_text(value))
        .encode('ascii', 'ignore')
        .decode('ascii')
    )
    return re.sub(r'[^a-z0-9]+', ' ', ascii_text.lower()).strip()


def first_item(value):
    """Prend le premier élément d'une cellule contenant plusieurs valeurs."""
    return re.split(r'[;|]', as_text(value), maxsplit=1)[0].strip()


def truncate(value, max_length):
    return as_text(value)[:max_length]


def bool_value(value):
    return normalize(value) in TRUE_VALUES


def decimal_value(value):
    try:
        return Decimal(as_text(value)).quantize(
            Decimal('0.000001'), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError):
        return None


def int_value(value):
    try:
        return int(float(as_text(value)))
    except (TypeError, ValueError):
        return None


def clean_email(value):
    email = re.split(r'[\s,;]+', first_item(value))[0].strip().lower()
    return email if '@' in email else None


def clean_url(value):
    url = first_item(value)
    if not url or '@' in url or re.search(r'\s', url):
        return None
    if re.match(r'^https?://', url, re.I):
        return truncate(url, 200)
    if URL_RE.match(url):
        return truncate('https://' + url, 200)
    return None


def specialisation(value):
    normalized = normalize(value)
    if 'specialiste' in normalized:
        return 'specialiste'
    return 'generaliste'


def derive_source(value):
    if 'enquetee' in normalize(value):
        return 'enquetee'
    return 'revue_documentaire'


def derive_typologie(row, flags):
    labels = (
        (flags['est_incubateur'], 'Incubateur'),
        (flags['est_accelerateur'], 'Accélérateur'),
        (flags['est_recherche_innovation'], 'Recherche innovation'),
        (flags['est_appui_technique'], 'Appui technique'),
        (flags['est_structure_financement'], 'Financement'),
        (flags['est_plateforme_reseau'], 'Plateforme réseau'),
    )
    active = [label for enabled, label in labels if enabled]
    if active:
        return truncate(' | '.join(active), 120)
    return truncate(
        first_item(row.get('types_structure'))
        or first_item(row.get('categorie_annuaire'))
        or 'incubateur',
        120,
    )


class Command(BaseCommand):
    help = (
        "Peuple la base avec les SAEI du XLSX unifié et crée un compte SAEI "
        "approuvé par structure (emails fictifs séquentiels, mot de passe commun)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', type=Path, default=DEFAULT_XLSX,
            help='Chemin du fichier XLSX (défaut : le fichier de backend/data).',
        )
        parser.add_argument('--sheet', default='SAEI', help='Feuille à lire.')
        parser.add_argument(
            '--password', default='Saei@2026',
            help='Mot de passe commun attribué à tous les comptes SAEI.',
        )
        parser.add_argument('--email-prefix', default='saei', help='Préfixe des emails fictifs.')
        parser.add_argument('--email-domain', default='example.com', help='Domaine des emails fictifs.')
        parser.add_argument('--start-index', type=int, default=1, help='Premier index des emails.')
        parser.add_argument(
            '--skip-existing', action='store_true',
            help='Ne pas écraser les structures déjà présentes en base.',
        )

    def handle(self, *args, **options):
        records = self._read_rows(options['file'], options['sheet'])
        if not records:
            raise CommandError('Aucune structure trouvée dans la feuille.')

        stats = {
            'structures_created': 0,
            'structures_updated': 0,
            'villes_created': 0,
            'users_created': 0,
            'users_updated': 0,
            'profiles_created': 0,
            'profiles_updated': 0,
        }

        with transaction.atomic():
            for index, (excel_line, row) in enumerate(
                records, start=options['start_index']
            ):
                self._import_row(row, excel_line, index, options, stats)

        self.stdout.write(self.style.SUCCESS(
            f"Import terminé : {len(records)} lignes — "
            f"{stats['structures_created']} structures créées, "
            f"{stats['structures_updated']} mises à jour, "
            f"{stats['villes_created']} villes créées, "
            f"{stats['users_created']} comptes créés, "
            f"{stats['users_updated']} mis à jour, "
            f"{stats['profiles_created']} profils créés, "
            f"{stats['profiles_updated']} mis à jour."
        ))
        self.stdout.write(
            f"Comptes : {options['email_prefix']}NNN@{options['email_domain']} "
            f"(index {options['start_index']} à {options['start_index'] + len(records) - 1})"
        )
        self.stdout.write(f"Mot de passe commun : {options['password']}")

    # ------------------------------------------------------------------
    # Lecture du XLSX
    # ------------------------------------------------------------------
    def _read_rows(self, file_path, sheet_name):
        file_path = file_path.expanduser()
        if not file_path.is_file():
            raise CommandError(f'Fichier introuvable : {file_path}')

        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise CommandError(
                'La dépendance openpyxl est requise : pip install openpyxl'
            ) from exc

        workbook = load_workbook(file_path, read_only=True, data_only=True)
        try:
            if sheet_name not in workbook.sheetnames:
                raise CommandError(
                    f"Feuille '{sheet_name}' introuvable. "
                    f"Feuilles disponibles : {', '.join(workbook.sheetnames)}"
                )
            rows = workbook[sheet_name].iter_rows(values_only=True)
            try:
                headers = [as_text(header) for header in next(rows)]
            except StopIteration as exc:
                raise CommandError('La feuille est vide.') from exc

            missing = {'id', 'pays', 'nom_structure'} - set(headers)
            if missing:
                raise CommandError(
                    f'Colonnes manquantes : {", ".join(sorted(missing))}'
                )

            records = []
            for excel_line, values in enumerate(rows, start=2):
                if not any(value is not None for value in values):
                    continue
                row = dict(zip(headers, values))
                if not as_text(row.get('nom_structure')):
                    continue
                records.append((excel_line, row))
            return records
        finally:
            workbook.close()

    # ------------------------------------------------------------------
    # Import d'une ligne
    # ------------------------------------------------------------------
    def _import_row(self, row, excel_line, index, options, stats):
        identifier = as_text(row.get('id')) or f'{index:03d}'
        nom = truncate(row.get('nom_structure'), 200)
        pays = PAYS_MAP.get(normalize(row.get('pays')))
        if pays is None:
            raise CommandError(
                f"Ligne {excel_line} : pays inconnu '{as_text(row.get('pays'))}'."
            )

        ville, ville_created = self._resolve_ville(row)
        if ville_created:
            stats['villes_created'] += 1

        telephone = (
            first_item(row.get('telephone_structure'))
            or first_item(row.get('contact_telephone'))
        )
        flags = {
            'est_incubateur': bool_value(row.get('est_incubateur')),
            'est_accelerateur': bool_value(row.get('est_accelerateur')),
            'est_recherche_innovation': bool_value(row.get('est_recherche_innovation')),
            'est_appui_technique': bool_value(row.get('est_appui_technique')),
            'est_structure_financement': bool_value(row.get('est_structure_financement')),
            'est_plateforme_reseau': bool_value(row.get('est_plateforme_reseau')),
        }
        structure_defaults = {
            'ville_siege': ville,
            'latitude': decimal_value(row.get('latitude')),
            'longitude': decimal_value(row.get('longitude')),
            'service': truncate(row.get('services'), 200),
            'public_cible': truncate(row.get('publics_cibles'), 200),
            'stade': truncate(row.get('stades_intervention'), 200),
            'besoin_couvert': truncate(row.get('besoins_non_couverts'), 200),
            'typologie': derive_typologie(row, flags),
            'specialisation': specialisation(row.get('profil_specialisation')),
            'zone_intervention': truncate(row.get('zone_intervention'), 100),
            'site_web': clean_url(row.get('site_web')),
            'email_structure': clean_email(row.get('email_structure')),
            'telephone_structure': truncate(telephone, 30),
            'contact_nom': truncate(row.get('contact_nom'), 150),
            'contact_fonction': truncate(row.get('contact_fonction'), 150),
            'contact_email': clean_email(row.get('contact_email')),
            'contact_telephone': truncate(row.get('contact_telephone'), 30),
            'region_departement': truncate(row.get('region_departement'), 100),
            'acronyme': truncate(row.get('acronyme'), 200),
            'statut_juridique': truncate(
                as_text(row.get('statut_juridique'))
                or as_text(row.get('statut_juridique_precision')),
                100,
            ),
            'score_pertinence': int_value(row.get('score_iih')) or 0,
            'source': derive_source(row.get('niveau_donnees')),
            'est_publiee': True,
            **flags,
        }

        if options['skip_existing'] and Structure.objects.filter(
            pays=pays, nom=nom
        ).exists():
            structure = Structure.objects.get(pays=pays, nom=nom)
        else:
            structure, created = Structure.objects.update_or_create(
                pays=pays, nom=nom, defaults=structure_defaults
            )
            stats['structures_created' if created else 'structures_updated'] += 1

        email = (
            f"{options['email_prefix']}{index:03d}@{options['email_domain']}"
            .strip()
            .lower()
        )
        user = self._resolve_user(
            email, identifier, telephone, options['password']
        )
        stats['users_created' if user['created'] else 'users_updated'] += 1

        profile_defaults = {
            'structure': structure,
            'nom_structure_demandee': nom,
            'pays': pays,
            'ville': truncate(ville.nom if ville else '', 100),
            'telephone_structure': truncate(telephone, 30),
            'message': as_text(row.get('description')),
        }
        profile, profile_created = SaeiProfile.objects.update_or_create(
            user=user['instance'], defaults=profile_defaults
        )
        stats['profiles_created' if profile_created else 'profiles_updated'] += 1

    def _resolve_ville(self, row):
        ville_name = truncate(first_item(row.get('ville')), 200)
        if not ville_name:
            return None, False
        ville, created = Ville.objects.get_or_create(
            nom__iexact=ville_name,
            defaults={
                'nom': ville_name,
                'region': truncate(row.get('region_departement'), 100),
            },
        )
        return ville, created

    def _resolve_user(self, email, identifier, telephone, password):
        user_defaults = {
            'first_name': 'SAEI',
            'last_name': truncate(identifier, 150),
            'phone': truncate(telephone, 30),
            'role': Role.SAEI,
            'status': Status.APPROVED,
            'is_active': True,
            'is_staff': False,
            'is_superuser': False,
        }

        user = User.objects.filter(email=email).first()
        if user is None:
            user = User(email=email)
            for field, value in user_defaults.items():
                setattr(user, field, value)
            user.set_password(password)
            user.save()
            return {'instance': user, 'created': True}

        if user.role != Role.SAEI:
            raise CommandError(
                f"L'email {email} appartient déjà à un compte {user.role}."
            )

        changed = False
        for field, value in user_defaults.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed = True
        if not user.check_password(password):
            user.set_password(password)
            changed = True
        if changed:
            user.save()
        return {'instance': user, 'created': False}

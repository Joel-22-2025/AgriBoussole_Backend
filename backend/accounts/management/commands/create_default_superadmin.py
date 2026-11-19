"""Crée l'administrateur initial à partir des variables d'environnement."""

from django.conf import settings
from django.core.management.base import BaseCommand

from accounts.models import Role, Status, User


class Command(BaseCommand):
    """Commande idempotente utilisée lors du déploiement sur Render."""

    help = "Crée ou met à jour le compte administrateur défini dans le .env."

    def handle(self, *args: object, **options: object) -> None:
        """Applique les identifiants ADMIN par défaut s'ils sont renseignés."""
        email = getattr(settings, 'DEFAULT_SUPERADMIN_EMAIL', '')
        password = getattr(settings, 'DEFAULT_SUPERADMIN_PASSWORD', '')

        if not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    'DEFAULT_SUPERADMIN_EMAIL / DEFAULT_SUPERADMIN_PASSWORD non définis : '
                    'aucun administrateur créé.'
                )
            )
            return

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            User.objects.create_superuser(
                email=email,
                password=password,
                first_name='Administrateur',
            )
            self.stdout.write(self.style.SUCCESS(f'Administrateur créé : {email}'))
            return

        user.role = Role.ADMIN
        user.status = Status.APPROVED
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save(update_fields=[
            'role',
            'status',
            'is_staff',
            'is_superuser',
            'is_active',
            'password',
        ])
        self.stdout.write(self.style.SUCCESS(f'Administrateur mis à jour : {email}'))

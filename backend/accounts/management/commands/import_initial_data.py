"""Importe un fixture JSON depuis un fichier local ou une URL HTTPS."""

import os
from pathlib import Path

import requests
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Charge la fixture de données dans la base de l'environnement courant."""

    help = "Importe accounts/structures/engagement depuis un fichier ou DATA_FIXTURE_URL."

    def add_arguments(self, parser):
        parser.add_argument('--input', type=str, help='Chemin local vers le fixture JSON.')
        parser.add_argument('--url', type=str, help='URL HTTPS du fixture JSON.')

    def handle(self, *args: object, **options: object) -> None:
        url = options.get('url') or os.environ.get('DATA_FIXTURE_URL', '')
        input_path = options.get('input')

        if url:
            self.stdout.write('Téléchargement de la fixture…')
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            target = settings.BASE_DIR / 'data' / 'downloaded_initial_data.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
            fixture = str(target)
        elif input_path:
            fixture = input_path
        else:
            fixture = str(settings.BASE_DIR / 'data' / 'initial_data.json')
            if not Path(fixture).exists():
                self.stdout.write(
                    self.style.WARNING('Aucune fixture fournie : import ignoré.')
                )
                return

        call_command('loaddata', fixture, verbosity=options.get('verbosity', 1))
        self.stdout.write(self.style.SUCCESS(f'Import terminé : {fixture}'))

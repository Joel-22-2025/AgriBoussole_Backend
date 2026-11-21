"""Exporte les données métier locales vers un fixture JSON transportable."""

from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Crée un fixture accounts + structures + engagement depuis la base courante."""

    help = "Exporte la base locale vers backend/data/initial_data.json."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default=str(settings.BASE_DIR / 'data' / 'initial_data.json'),
        )

    def handle(self, *args: object, **options: object) -> None:
        output = Path(options['output'])
        output.parent.mkdir(parents=True, exist_ok=True)
        call_command(
            'dumpdata',
            'accounts',
            'structures',
            'engagement',
            natural_primary=True,
            natural_foreign=True,
            indent=2,
            output=str(output),
        )
        raw = output.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('cp1252')
        output.write_text(text, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Export terminé : {output}'))

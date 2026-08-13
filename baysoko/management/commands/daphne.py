import os
import sys
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run the project using Daphne ASGI server.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--bind',
            default='0.0.0.0',
            help='The interface to bind Daphne to (default: 0.0.0.0).'
        )
        parser.add_argument(
            '--port',
            default=os.environ.get('PORT', '8000'),
            help='The port Daphne should listen on (default: env PORT or 8000).'
        )
        parser.add_argument(
            '--app',
            default='baysoko.asgi:application',
            help='The ASGI app path to run (default: baysoko.asgi:application).'
        )
        parser.add_argument(
            '--verbosity',
            type=int,
            choices=[0, 1, 2, 3],
            default=1,
            help='Verbosity level for Daphne output.',
        )

    def handle(self, *args, **options):
        bind = options['bind']
        port = options['port']
        app = options['app']
        verbosity = options['verbosity']

        # Prefer the installed daphne executable if available.
        daphne_cmd = shutil.which('daphne') if 'shutil' in globals() else None
        if not daphne_cmd:
            try:
                import shutil
                daphne_cmd = shutil.which('daphne')
            except Exception:
                daphne_cmd = None

        if not daphne_cmd:
            self.stderr.write(self.style.ERROR(
                'Daphne is not installed or not on PATH. Install daphne via requirements.txt or pip install daphne.'
            ))
            raise SystemExit(1)

        cmd = [daphne_cmd, '-b', bind, '-p', str(port), app]
        if verbosity == 0:
            cmd.append('--verbosity=0')
        elif verbosity == 2:
            cmd.append('--verbosity=2')
        elif verbosity == 3:
            cmd.append('--verbosity=3')

        os.execvp(daphne_cmd, cmd)

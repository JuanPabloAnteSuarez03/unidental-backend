from django.core.management.base import BaseCommand, CommandError
from django.core import management

class Command(BaseCommand):
    help = 'Limpia toda la base de datos e importa productos, clientes y proveedores desde los CSVs estándar.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simula la importación sin aplicar cambios.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        flags_db = []
        flags_sup = []
        flags_cli = []
        if dry_run:
            flags_db.append('--dry-run')
            flags_sup.append('--dry-run')
            flags_cli.append('--dry-run')
        else:
            flags_db.append('--clear-data')
            flags_sup.append('--clean')
            flags_cli.append('--clean')

        self.stdout.write(self.style.WARNING('LIMPIANDO E IMPORTANDO TODA LA BASE DE DATOS...'))

        # 1. Productos (esto limpia toda la base si se usa --clear-data)
        management.call_command(
            'populate_database_fast',
            'UNIDENTAL - COMPRAS E INV (1).csv',
            *flags_db
        )

        # 2. Proveedores
        management.call_command(
            'populate_suppliers',
            '--file', 'UNIDENTAL (1) - PROVEEDORES 2024.csv',
            *flags_sup
        )

        # 3. Clientes
        management.call_command(
            'populate_customers',
            '--file', 'UNIDENTAL (1) - BASE DATOS  .csv',
            *flags_cli
        )

        self.stdout.write(self.style.SUCCESS('¡Importación completa!')) 
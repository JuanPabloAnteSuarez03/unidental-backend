from django.core.management.base import BaseCommand
from django.db import transaction
from sales.models import Sale, Return, ReturnItem
from sales.models import update_inventory_on_return_item_delete, update_return_total
from django.db.models.signals import post_delete


class Command(BaseCommand):
    help = 'Deletes all sales, returns, and related data from the database, disabling inventory signals.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting the deletion process...'))

        # Desconectar señales para evitar validaciones de inventario
        post_delete.disconnect(update_inventory_on_return_item_delete, sender=ReturnItem)
        post_delete.disconnect(update_return_total, sender=ReturnItem)
        self.stdout.write(self.style.NOTICE('Temporarily disconnected inventory signals for ReturnItem.'))

        try:
            # Get counts before deletion
            returns_count = Return.objects.count()
            sales_count = Sale.objects.count()

            if returns_count == 0 and sales_count == 0:
                self.stdout.write(self.style.SUCCESS('No sales or returns to delete.'))
                return

            # Deleting Returns first due to PROTECT constraint on Sale
            if returns_count > 0:
                self.stdout.write(f'Deleting {returns_count} returns...')
                Return.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('All returns have been deleted.'))
            else:
                self.stdout.write('No returns to delete.')
            
            # Deleting Sales
            if sales_count > 0:
                self.stdout.write(f'Deleting {sales_count} sales...')
                Sale.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('All sales have been deleted.'))
            else:
                self.stdout.write('No sales to delete.')

            self.stdout.write(self.style.SUCCESS('Operation completed successfully.'))

        finally:
            # Reconectar señales
            post_delete.connect(update_inventory_on_return_item_delete, sender=ReturnItem)
            post_delete.connect(update_return_total, sender=ReturnItem)
            self.stdout.write(self.style.NOTICE('Reconnected inventory signals.')) 
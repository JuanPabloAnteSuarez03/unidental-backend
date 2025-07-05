"""
Comando para crear cuentas de crédito vencidas de prueba.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from suppliers.models import Supplier
from purchases.models import PurchaseOrder
from credits.models import CreditPurchaseAccount
from inventory.models import Location


class Command(BaseCommand):
    help = 'Crea cuentas de crédito vencidas de prueba para testing'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Creando cuentas de crédito vencidas de prueba...')
        )

        # Obtener o crear una ubicación por defecto
        default_location, _ = Location.objects.get_or_create(
            name='Almacén Principal',
            defaults={
                'type': 'bodega',
                'address': 'Calle Principal #123'
            }
        )

        # Crear proveedores con números de teléfono
        suppliers_data = [
            {
                'name': 'Proveedor Urgente SAS',
                'contact_name': 'Carlos Rodríguez',
                'phone': '3001234567',
                'email': 'carlos@urgente.com',
                'days_overdue': 20,
                'amount': Decimal('1500000')
            },
            {
                'name': 'Distribuidora El Rapidito',
                'contact_name': 'María González',
                'phone': '3157654321',
                'email': 'maria@rapidito.com',
                'days_overdue': 12,
                'amount': Decimal('850000')
            },
            {
                'name': 'Suministros Médicos SA',
                'contact_name': 'Juan Pérez',
                'phone': '3209876543',
                'email': 'juan@medicos.com',
                'days_overdue': 8,
                'amount': Decimal('2200000')
            },
            {
                'name': 'Importadora Dental Ltda',
                'contact_name': 'Ana Martínez',
                'phone': '3118765432',
                'email': 'ana@dental.com',
                'days_overdue': 3,
                'amount': Decimal('650000')
            },
            {
                'name': 'Proveedor Sin Teléfono',
                'contact_name': 'Luis García',
                'phone': None,  # Sin teléfono para testing
                'email': 'luis@sintel.com',
                'days_overdue': 15,
                'amount': Decimal('900000')
            }
        ]

        created_accounts = []

        for supplier_data in suppliers_data:
            # Crear o obtener el proveedor
            supplier, created = Supplier.objects.get_or_create(
                name=supplier_data['name'],
                defaults={
                    'contact_name': supplier_data['contact_name'],
                    'phone': supplier_data['phone'],
                    'email': supplier_data['email']
                }
            )
            
            if created:
                self.stdout.write(f'✓ Proveedor creado: {supplier.name}')
            else:
                self.stdout.write(f'  Proveedor existente: {supplier.name}')

            # Crear orden de compra ficticia
            purchase_order, po_created = PurchaseOrder.objects.get_or_create(
                supplier=supplier,
                destination=default_location,
                defaults={
                    'order_date': date.today() - timedelta(days=30),
                    'status': 'received',
                    'notes': f'Orden de prueba para crédito - {supplier_data["amount"]}'
                }
            )

            if po_created:
                self.stdout.write(f'✓ Orden de compra creada: {purchase_order.id}')

            # Crear cuenta de crédito vencida
            overdue_date = date.today() - timedelta(days=supplier_data['days_overdue'])
            
            credit_account, ca_created = CreditPurchaseAccount.objects.get_or_create(
                purchase_order=purchase_order,
                defaults={
                    'original_amount': supplier_data['amount'],
                    'remaining_amount': supplier_data['amount'],
                    'start_date': overdue_date - timedelta(days=30),
                    'payment_frequency': 'monthly',
                    'next_payment_date': overdue_date,
                    'payment_amount': supplier_data['amount'] / 3,  # Pago en 3 cuotas
                    'grace_days': 3,
                    'is_active': True,
                    'notes': f'Cuenta de prueba - {supplier_data["days_overdue"]} días vencido'
                }
            )

            if ca_created:
                created_accounts.append(credit_account)
                self.stdout.write(
                    f'✓ Cuenta de crédito creada: ${credit_account.remaining_amount:,.0f} - '
                    f'{supplier_data["days_overdue"]} días vencido'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n¡Completado! Se crearon {len(created_accounts)} cuentas de crédito vencidas de prueba.'
            )
        )
        
        self.stdout.write(
            self.style.WARNING(
                '\nPuedes ver los resultados en: http://127.0.0.1:8000/api/credits/overdue-debts/'
            )
        )
        
        self.stdout.write(
            self.style.WARNING(
                'API endpoint: http://127.0.0.1:8000/api/credits/purchase-accounts/overdue_with_whatsapp/'
            )
        ) 
"""
Comando para crear cuentas de crédito próximas a vencer para prueba de recordatorios preventivos.
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
    help = 'Crea cuentas de crédito próximas a vencer para testing de recordatorios preventivos'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Creando cuentas de crédito próximas a vencer...')
        )

        # Obtener o crear una ubicación por defecto
        default_location, _ = Location.objects.get_or_create(
            name='Almacén Principal',
            defaults={
                'type': 'bodega',
                'address': 'Calle Principal #123'
            }
        )

        # Crear proveedores con fechas próximas a vencer
        upcoming_suppliers_data = [
            {
                'name': 'Proveedor Próximo 1',
                'contact_name': 'Sandra López',
                'phone': '3501234567',
                'email': 'sandra@proximo1.com',
                'days_until_due': 1,  # Vence mañana
                'amount': Decimal('750000')
            },
            {
                'name': 'Proveedor Próximo 2',
                'contact_name': 'Miguel Torres',
                'phone': '3007654321',
                'email': 'miguel@proximo2.com',
                'days_until_due': 2,  # Vence en 2 días
                'amount': Decimal('1200000')
            },
            {
                'name': 'Proveedor Próximo 3',
                'contact_name': 'Elena Ruiz',
                'phone': '3159876543',
                'email': 'elena@proximo3.com',
                'days_until_due': 3,  # Vence en 3 días
                'amount': Decimal('980000')
            },
            {
                'name': 'Proveedor Vence Hoy',
                'contact_name': 'Roberto Silva',
                'phone': '3208765432',
                'email': 'roberto@hoy.com',
                'days_until_due': 0,  # Vence hoy
                'amount': Decimal('1800000')
            }
        ]

        created_accounts = []

        for supplier_data in upcoming_suppliers_data:
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
                    'order_date': date.today() - timedelta(days=20),
                    'status': 'received',
                    'notes': f'Orden de prueba próxima a vencer - {supplier_data["amount"]}'
                }
            )

            if po_created:
                self.stdout.write(f'✓ Orden de compra creada: {purchase_order.id}')

            # Crear cuenta de crédito próxima a vencer
            due_date = date.today() + timedelta(days=supplier_data['days_until_due'])
            
            credit_account, ca_created = CreditPurchaseAccount.objects.get_or_create(
                purchase_order=purchase_order,
                defaults={
                    'original_amount': supplier_data['amount'],
                    'remaining_amount': supplier_data['amount'],
                    'start_date': date.today() - timedelta(days=20),
                    'payment_frequency': 'monthly',
                    'next_payment_date': due_date,
                    'payment_amount': supplier_data['amount'] / 2,  # Pago en 2 cuotas
                    'grace_days': 3,
                    'is_active': True,
                    'notes': f'Cuenta de prueba - vence en {supplier_data["days_until_due"]} días'
                }
            )

            if ca_created:
                created_accounts.append(credit_account)
                days_text = {
                    0: 'hoy',
                    1: 'mañana',
                    2: 'en 2 días',
                    3: 'en 3 días'
                }.get(supplier_data['days_until_due'], f'en {supplier_data["days_until_due"]} días')
                
                self.stdout.write(
                    f'✓ Cuenta de crédito creada: ${credit_account.remaining_amount:,.0f} - '
                    f'vence {days_text}'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n¡Completado! Se crearon {len(created_accounts)} cuentas próximas a vencer.'
            )
        )
        
        self.stdout.write(
            self.style.WARNING(
                '\nPuedes ver todos los recordatorios en:'
            )
        )
        
        self.stdout.write(
            self.style.WARNING(
                'API endpoint: http://127.0.0.1:8000/api/credits/purchase-accounts/overdue_with_whatsapp/'
            )
        )
        
        self.stdout.write(
            self.style.WARNING(
                'Solo vencidos: http://127.0.0.1:8000/api/credits/purchase-accounts/overdue_with_whatsapp/?include_upcoming=false'
            )
        ) 
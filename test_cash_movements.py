#!/usr/bin/env python
"""
Script de prueba para verificar los movimientos de caja.
Prueba los problemas de duplicación y el comportamiento de ajustes.
"""

import os
import sys
import django
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unidental.settings')
django.setup()

from cash.models import Cashes, Movements
from inventory.models import Location
from django.contrib.auth.models import User

def test_cash_movements():
    """Prueba los movimientos de caja para verificar que no hay duplicación."""
    
    print("=== PRUEBA DE MOVIMIENTOS DE CAJA ===\n")
    
    # Obtener o crear una sede y caja
    try:
        location = Location.objects.filter(type='sede').first()
        if not location:
            print("❌ No se encontró ninguna sede. Creando una...")
            location = Location.objects.create(
                name="Sede de Prueba",
                type='sede',
                address="Dirección de prueba"
            )
        
        cash, created = Cashes.objects.get_or_create(
            location=location,
            defaults={'balance': Decimal('0.00')}
        )
        
        if created:
            print(f"✅ Caja creada para {location.name}")
        else:
            print(f"✅ Caja existente para {location.name}")
        
        print(f"Saldo inicial: ${cash.balance:,.2f}\n")
        
        # Obtener o crear un usuario
        user, created = User.objects.get_or_create(
            username='test_user',
            defaults={'email': 'test@example.com'}
        )
        
        # PRUEBA 1: Ingreso de $1000
        print("--- PRUEBA 1: Ingreso de $1000 ---")
        initial_balance = cash.balance
        
        movement1 = Movements.objects.create(
            cash=cash,
            movement_type='ingreso',
            amount=Decimal('1000.00'),
            reference_type='ajuste_manual',
            notes='Prueba de ingreso',
            created_by=user
        )
        
        cash.refresh_from_db()
        print(f"Saldo después del ingreso: ${cash.balance:,.2f}")
        print(f"Saldo esperado: ${initial_balance + Decimal('1000.00'):,.2f}")
        
        if cash.balance == initial_balance + Decimal('1000.00'):
            print("✅ Ingreso correcto - no hay duplicación")
        else:
            print("❌ ERROR: Hay duplicación en el ingreso")
        
        print()
        
        # PRUEBA 2: Egreso de $300
        print("--- PRUEBA 2: Egreso de $300 ---")
        balance_before_egreso = cash.balance
        
        movement2 = Movements.objects.create(
            cash=cash,
            movement_type='egreso',
            amount=Decimal('300.00'),
            reference_type='ajuste_manual',
            notes='Prueba de egreso',
            created_by=user
        )
        
        cash.refresh_from_db()
        print(f"Saldo después del egreso: ${cash.balance:,.2f}")
        print(f"Saldo esperado: ${balance_before_egreso - Decimal('300.00'):,.2f}")
        
        if cash.balance == balance_before_egreso - Decimal('300.00'):
            print("✅ Egreso correcto - no hay duplicación")
        else:
            print("❌ ERROR: Hay duplicación en el egreso")
        
        print()
        
        # PRUEBA 3: Ajuste a $500
        print("--- PRUEBA 3: Ajuste a $500 ---")
        balance_before_ajuste = cash.balance
        
        movement3 = Movements.objects.create(
            cash=cash,
            movement_type='ajuste',
            amount=Decimal('500.00'),
            reference_type='ajuste_manual',
            notes='Prueba de ajuste',
            created_by=user
        )
        
        cash.refresh_from_db()
        print(f"Saldo después del ajuste: ${cash.balance:,.2f}")
        print(f"Saldo esperado: $500.00")
        
        if cash.balance == Decimal('500.00'):
            print("✅ Ajuste correcto - sustituye el valor")
        else:
            print("❌ ERROR: El ajuste no sustituye el valor correctamente")
        
        print()
        
        # PRUEBA 4: Verificar que no hay duplicación en actualizaciones
        print("--- PRUEBA 4: Actualización de movimiento ---")
        balance_before_update = cash.balance
        
        # Actualizar el monto del primer movimiento
        old_amount = movement1.amount
        movement1.amount = Decimal('1500.00')
        movement1.save()
        
        cash.refresh_from_db()
        print(f"Saldo después de actualizar ingreso de ${old_amount} a $1500: ${cash.balance:,.2f}")
        print(f"Saldo esperado: ${balance_before_update + Decimal('500.00'):,.2f}")
        
        if cash.balance == balance_before_update + Decimal('500.00'):
            print("✅ Actualización correcta - no hay duplicación")
        else:
            print("❌ ERROR: Hay duplicación en la actualización")
        
        print()
        
        # Resumen final
        print("=== RESUMEN FINAL ===")
        print(f"Saldo final de la caja: ${cash.balance:,.2f}")
        print(f"Total de movimientos: {cash.movements.count()}")
        
        # Mostrar todos los movimientos
        print("\nMovimientos realizados:")
        for i, movement in enumerate(cash.movements.all().order_by('created_at'), 1):
            print(f"{i}. {movement.get_movement_type_display()} - ${movement.amount:,.2f} - {movement.notes}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error durante la prueba: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_cash_movements()
    if success:
        print("\n🎉 Todas las pruebas pasaron correctamente!")
    else:
        print("\n💥 Algunas pruebas fallaron!")
        sys.exit(1) 
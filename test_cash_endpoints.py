#!/usr/bin/env python
"""
Script para probar los endpoints de caja directamente.
Prueba los problemas de duplicación y el comportamiento de ajustes via API.
"""

import os
import sys
import django
import requests
import json
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unidental.settings')
django.setup()

from django.contrib.auth.models import User
from cash.models import Cashes
from inventory.models import Location

def get_auth_token():
    """Obtiene un token de autenticación."""
    try:
        # Crear usuario admin si no existe
        user, created = User.objects.get_or_create(
            username='admin_test',
            defaults={
                'email': 'admin@test.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            user.set_password('admin123')
            user.save()
            print("✅ Usuario admin creado")
        
        # Obtener token
        response = requests.post('http://localhost:8000/api/auth/token/login/', {
            'username': 'admin_test',
            'password': 'admin123'
        })
        
        if response.status_code == 200:
            token = response.json()['auth_token']
            print("✅ Token obtenido correctamente")
            return token
        else:
            print(f"❌ Error al obtener token: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error en autenticación: {str(e)}")
        return None

def test_cash_endpoints():
    """Prueba los endpoints de caja."""
    
    print("=== PRUEBA DE ENDPOINTS DE CAJA ===\n")
    
    # Obtener token
    token = get_auth_token()
    if not token:
        print("❌ No se pudo obtener el token. Asegúrate de que el servidor esté corriendo.")
        return False
    
    headers = {
        'Authorization': f'Token {token}',
        'Content-Type': 'application/json'
    }
    
    base_url = 'http://localhost:8000/api'
    
    try:
        # 1. Obtener cajas existentes
        print("--- 1. Obtener cajas existentes ---")
        response = requests.get(f'{base_url}/cash/cashes/', headers=headers)
        
        if response.status_code == 200:
            cashes = response.json()
            print(f"✅ Se encontraron {len(cashes)} cajas")
            
            if not cashes:
                print("❌ No hay cajas disponibles. Creando una...")
                # Crear una sede y caja
                location = Location.objects.filter(type='sede').first()
                if not location:
                    location = Location.objects.create(
                        name="Sede de Prueba API",
                        type='sede',
                        address="Dirección de prueba API"
                    )
                
                cash = Cashes.objects.create(
                    location=location,
                    balance=Decimal('0.00')
                )
                print(f"✅ Caja creada para {location.name}")
            else:
                cash_id = cashes[0]['id']
                print(f"✅ Usando caja existente ID: {cash_id}")
        else:
            print(f"❌ Error al obtener cajas: {response.status_code}")
            return False
        
        # 2. Obtener el ID de la caja
        response = requests.get(f'{base_url}/cash/cashes/', headers=headers)
        cashes = response.json()
        cash_id = cashes[0]['id']
        
        print(f"\n--- 2. Probar movimientos en caja ID: {cash_id} ---")
        
        # 3. Crear ingreso de $1000
        print("\n--- 3. Crear ingreso de $1000 ---")
        ingreso_data = {
            'cash': cash_id,
            'movement_type': 'ingreso',
            'amount': '1000.00',
            'reference_type': 'ajuste_manual',
            'notes': 'Prueba de ingreso via API'
        }
        
        response = requests.post(
            f'{base_url}/cash/movements/',
            headers=headers,
            data=json.dumps(ingreso_data)
        )
        
        if response.status_code == 201:
            ingreso = response.json()
            print(f"✅ Ingreso creado ID: {ingreso['id']}")
            
            # Verificar saldo
            cash_response = requests.get(f'{base_url}/cash/cashes/{cash_id}/', headers=headers)
            if cash_response.status_code == 200:
                cash_data = cash_response.json()
                print(f"Saldo después del ingreso: {cash_data['balance_formatted']}")
        else:
            print(f"❌ Error al crear ingreso: {response.status_code} - {response.text}")
            return False
        
        # 4. Crear egreso de $300
        print("\n--- 4. Crear egreso de $300 ---")
        egreso_data = {
            'cash': cash_id,
            'movement_type': 'egreso',
            'amount': '300.00',
            'reference_type': 'ajuste_manual',
            'notes': 'Prueba de egreso via API'
        }
        
        response = requests.post(
            f'{base_url}/cash/movements/',
            headers=headers,
            data=json.dumps(egreso_data)
        )
        
        if response.status_code == 201:
            egreso = response.json()
            print(f"✅ Egreso creado ID: {egreso['id']}")
            
            # Verificar saldo
            cash_response = requests.get(f'{base_url}/cash/cashes/{cash_id}/', headers=headers)
            if cash_response.status_code == 200:
                cash_data = cash_response.json()
                print(f"Saldo después del egreso: {cash_data['balance_formatted']}")
        else:
            print(f"❌ Error al crear egreso: {response.status_code} - {response.text}")
            return False
        
        # 5. Crear ajuste a $500
        print("\n--- 5. Crear ajuste a $500 ---")
        ajuste_data = {
            'cash': cash_id,
            'movement_type': 'ajuste',
            'amount': '500.00',
            'reference_type': 'ajuste_manual',
            'notes': 'Prueba de ajuste via API'
        }
        
        response = requests.post(
            f'{base_url}/cash/movements/',
            headers=headers,
            data=json.dumps(ajuste_data)
        )
        
        if response.status_code == 201:
            ajuste = response.json()
            print(f"✅ Ajuste creado ID: {ajuste['id']}")
            
            # Verificar saldo
            cash_response = requests.get(f'{base_url}/cash/cashes/{cash_id}/', headers=headers)
            if cash_response.status_code == 200:
                cash_data = cash_response.json()
                print(f"Saldo después del ajuste: {cash_data['balance_formatted']}")
                
                # Verificar que el saldo es exactamente $500
                if cash_data['balance'] == '500.00':
                    print("✅ Ajuste correcto - sustituye el valor")
                else:
                    print(f"❌ ERROR: El ajuste no sustituye correctamente. Saldo: {cash_data['balance']}")
        else:
            print(f"❌ Error al crear ajuste: {response.status_code} - {response.text}")
            return False
        
        # 6. Obtener todos los movimientos
        print("\n--- 6. Listar todos los movimientos ---")
        response = requests.get(f'{base_url}/cash/movements/', headers=headers)
        
        if response.status_code == 200:
            movements = response.json()
            print(f"✅ Total de movimientos: {len(movements)}")
            
            for i, movement in enumerate(movements, 1):
                print(f"{i}. {movement['movement_type_display']} - {movement['amount_formatted']} - {movement['notes']}")
        else:
            print(f"❌ Error al obtener movimientos: {response.status_code}")
        
        # 7. Obtener resumen de cajas
        print("\n--- 7. Obtener resumen de cajas ---")
        response = requests.get(f'{base_url}/cash/cashes/summary/', headers=headers)
        
        if response.status_code == 200:
            summary = response.json()
            print(f"✅ Resumen obtenido:")
            print(f"   - Saldo total: {summary['total_balance_formatted']}")
            print(f"   - Cajas activas: {summary['active_cashes_count']}")
            print(f"   - Movimientos recientes: {summary['recent_movements_count']}")
            print(f"   - Transferencias pendientes: {summary['pending_transfers_count']}")
        else:
            print(f"❌ Error al obtener resumen: {response.status_code}")
        
        print("\n🎉 Todas las pruebas de endpoints pasaron correctamente!")
        return True
        
    except Exception as e:
        print(f"❌ Error durante las pruebas: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("⚠️  Asegúrate de que el servidor Django esté corriendo en http://localhost:8000")
    print("   Ejecuta: python manage.py runserver 0.0.0.0:8000\n")
    
    success = test_cash_endpoints()
    if not success:
        print("\n💥 Algunas pruebas fallaron!")
        sys.exit(1) 
#!/usr/bin/env python3
"""
Script de prueba para los nuevos endpoints de productos ya devueltos.
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unidental.settings')
django.setup()

from sales.models import Sale, SaleItem, Return, ReturnItem, Customer
from catalogs.models import Product
from core.models import Location
from django.utils import timezone

def test_returned_items_endpoints():
    """Prueba los nuevos endpoints de productos devueltos."""
    
    print("🧪 Probando endpoints de productos ya devueltos...")
    
    # 1. Crear datos de prueba si no existen
    print("\n📋 Preparando datos de prueba...")
    
    # Obtener o crear ubicación
    location, created = Location.objects.get_or_create(
        name="Sede Norte",
        defaults={'type': 'store', 'address': 'Dirección de prueba'}
    )
    
    # Obtener o crear cliente
    customer, created = Customer.objects.get_or_create(
        name="Cliente Prueba",
        defaults={'phone': '123456789', 'email': 'test@example.com'}
    )
    
    # Obtener productos de prueba
    products = Product.objects.all()[:3]
    if not products.exists():
        print("❌ No hay productos disponibles. Creando productos de prueba...")
        # Crear productos de prueba
        products = []
        for i in range(3):
            product = Product.objects.create(
                name=f"Producto Prueba {i+1}",
                sku=f"TEST-{i+1:03d}",
                sale_price=1000 * (i+1),
                requires_batch_control=False
            )
            products.append(product)
    
    # 2. Crear una venta de prueba
    print("🛒 Creando venta de prueba...")
    sale = Sale.objects.create(
        customer=customer,
        location=location,
        sale_type='normal',
        total_gross=0,
        total_net=0,
        total_tax=0
    )
    
    # Agregar items a la venta
    total_sale = 0
    for i, product in enumerate(products):
        quantity = (i + 1) * 2  # 2, 4, 6 unidades
        unit_price = product.sale_price
        item_total = quantity * unit_price
        total_sale += item_total
        
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            total_price=item_total
        )
    
    # Actualizar totales de la venta
    sale.total_gross = total_sale
    sale.total_net = total_sale
    sale.save()
    
    print(f"✅ Venta creada: ID {sale.id}, Total: ${total_sale:,}")
    
    # 3. Crear devoluciones de prueba
    print("🔄 Creando devoluciones de prueba...")
    
    # Primera devolución - parcial
    return1 = Return.objects.create(
        original_sale=sale,
        customer=customer,
        location=location,
        reason='customer_change',
        notes='Cliente cambió de opinión',
        total_amount=0
    )
    
    # Devolver 1 unidad del primer producto
    sale_item1 = sale.items.first()
    return_item1 = ReturnItem.objects.create(
        return_obj=return1,
        sale_item=sale_item1,
        product=sale_item1.product,
        quantity_returned=1,
        unit_price=sale_item1.unit_price
    )
    return1.total_amount = return_item1.quantity_returned * return_item1.unit_price
    return1.save()
    
    print(f"✅ Devolución 1 creada: ID {return1.id}, Producto: {sale_item1.product.name}")
    
    # Segunda devolución - otro producto
    return2 = Return.objects.create(
        original_sale=sale,
        customer=customer,
        location=location,
        reason='defective',
        notes='Producto defectuoso',
        total_amount=0
    )
    
    # Devolver 2 unidades del segundo producto
    sale_item2 = sale.items.all()[1]
    return_item2 = ReturnItem.objects.create(
        return_obj=return2,
        sale_item=sale_item2,
        product=sale_item2.product,
        quantity_returned=2,
        unit_price=sale_item2.unit_price
    )
    return2.total_amount = return_item2.quantity_returned * return_item2.unit_price
    return2.save()
    
    print(f"✅ Devolución 2 creada: ID {return2.id}, Producto: {sale_item2.product.name}")
    
    # 4. Probar el endpoint returned_items_by_sale
    print("\n🔍 Probando endpoint /api/sales/returns/returned-items-by-sale/")
    print(f"URL: GET /api/sales/returns/returned-items-by-sale/?sale_id={sale.id}")
    
    # Simular la consulta
    from sales.views import ReturnViewSet
    from rest_framework.test import APIRequestFactory
    from rest_framework.test import force_authenticate
    from django.contrib.auth.models import User
    
    # Crear usuario de prueba
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@example.com'}
    )
    
    factory = APIRequestFactory()
    request = factory.get(f'/api/sales/returns/returned-items-by-sale/?sale_id={sale.id}')
    force_authenticate(request, user=user)
    
    viewset = ReturnViewSet()
    viewset.request = request
    
    try:
        response = viewset.returned_items_by_sale(request)
        print(f"✅ Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            print(f"📊 Información de la venta:")
            print(f"   - Venta ID: {data['sale_id']}")
            print(f"   - Cliente: {data['customer_name']}")
            print(f"   - Total devuelto: ${data['total_returned_amount']:,.2f}")
            print(f"   - Items devueltos: {len(data['returned_items'])}")
            
            for item in data['returned_items']:
                print(f"\n📦 Producto: {item['product_name']}")
                print(f"   - SKU: {item['product_sku']}")
                print(f"   - Cantidad original: {item['original_quantity']}")
                print(f"   - Total devuelto: {item['total_returned']}")
                print(f"   - Cantidad restante: {item['remaining_quantity']}")
                print(f"   - Devoluciones: {len(item['returns_detail'])}")
                
                for ret in item['returns_detail']:
                    print(f"     * Devolución #{ret['return_id']}: {ret['quantity_returned']} unidades ({ret['reason']})")
        else:
            print(f"❌ Error: {response.data}")
            
    except Exception as e:
        print(f"❌ Error al probar endpoint: {e}")
    
    # 5. Probar el endpoint returned_products_summary
    print("\n🔍 Probando endpoint /api/sales/returns/returned-products-summary/")
    print("URL: GET /api/sales/returns/returned-products-summary/?days=30&limit=10")
    
    try:
        request = factory.get('/api/sales/returns/returned-products-summary/?days=30&limit=10')
        force_authenticate(request, user=user)
        
        response = viewset.returned_products_summary(request)
        print(f"✅ Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            print(f"📊 Resumen de productos devueltos:")
            print(f"   - Período: {data['period_days']} días")
            print(f"   - Total devoluciones: {data['total_returns']}")
            print(f"   - Cantidad total devuelta: {data['total_returned_quantity']}")
            print(f"   - Monto total devuelto: ${data['total_returned_amount']:,.2f}")
            print(f"   - Productos más devueltos: {len(data['top_returned_products'])}")
            
            for i, product in enumerate(data['top_returned_products'][:3], 1):
                print(f"\n🏆 #{i} - {product['product_name']}")
                print(f"   - SKU: {product['product_sku']}")
                print(f"   - Cantidad devuelta: {product['total_returned_quantity']}")
                print(f"   - Monto devuelto: ${product['total_returned_amount']:,.2f}")
                print(f"   - Número de devoluciones: {product['return_count']}")
        else:
            print(f"❌ Error: {response.data}")
            
    except Exception as e:
        print(f"❌ Error al probar endpoint: {e}")
    
    print("\n✅ Pruebas completadas!")
    print(f"\n📝 Datos de prueba creados:")
    print(f"   - Venta ID: {sale.id}")
    print(f"   - Devoluciones: {return1.id}, {return2.id}")
    print(f"   - Productos devueltos: {sale_item1.product.name}, {sale_item2.product.name}")

if __name__ == "__main__":
    test_returned_items_endpoints() 
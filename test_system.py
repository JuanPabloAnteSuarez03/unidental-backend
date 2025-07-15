#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unidental.settings')
django.setup()

from catalogs.models import Product, ProductConversion
from inventory.models import InventoryStock, Location
from sales.models import Sale, SaleItem, Customer
from sales.serializers import SaleSerializer
from django.contrib.auth.models import User
import json
from decimal import Decimal

def test_system_status():
    """Verifica el estado del sistema después de la migración."""
    print("=== 🔍 ESTADO DEL SISTEMA ===")
    print(f"Total productos: {Product.objects.count()}")
    print(f"Productos simples: {Product.objects.filter(product_type='simple').count()}")
    print(f"Productos compuestos: {Product.objects.exclude(product_type='simple').count()}")
    print(f"Total conversiones: {ProductConversion.objects.count()}")
    
    print("\n=== 🔄 CONVERSIONES CREADAS ===")
    for conv in ProductConversion.objects.all():
        print(f"• {conv}")
    
    print("\n=== 📦 STOCK DISPONIBLE ===")
    for stock in InventoryStock.objects.filter(quantity__gt=0)[:10]:
        print(f"• {stock.product.name}: {stock.quantity} en {stock.location.name}")

def test_conversion_suggestions():
    """Testa las sugerencias de conversión."""
    print("\n=== 💡 TEST: SUGERENCIAS DE CONVERSIÓN ===")
    
    # Buscar un producto que tenga conversiones disponibles
    blister_products = Product.objects.filter(name__icontains='blister')
    if blister_products.exists():
        blister = blister_products.first()
        location = Location.objects.first()
        
        print(f"Buscando conversiones para: {blister.name}")
        
        # Obtener conversiones que pueden generar este producto
        reverse_conversions = ProductConversion.get_reverse_conversions(blister, location)
        
        print(f"Conversiones encontradas: {len(reverse_conversions)}")
        for conv in reverse_conversions:
            available_stock = InventoryStock.get_total_stock(conv.from_product, location)
            print(f"• {conv.from_product.name} → {conv.to_product.name}")
            print(f"  Factor: {conv.conversion_rate}, Stock disponible: {available_stock}")

def test_insufficient_stock_scenario():
    """Testa el escenario de stock insuficiente con sugerencias."""
    print("\n=== 🚨 TEST: ESCENARIO STOCK INSUFICIENTE ===")
    
    try:
        # Buscar un producto que NO requiera control de lotes y tenga stock 0
        products_no_batch = Product.objects.filter(
            requires_batch_control=False
        ).order_by('?')  # Orden aleatorio
        
        blister_product = None
        for product in products_no_batch:
            location = Location.objects.first()
            current_stock = InventoryStock.get_total_stock(product, location)
            if current_stock == 0:
                blister_product = product
                break
        
        if not blister_product:
            # Si no encontramos un producto con stock 0, usemos cualquiera sin control de lotes
            blister_product = products_no_batch.first()
            location = Location.objects.first()
            current_stock = InventoryStock.get_total_stock(blister_product, location)
        else:
            current_stock = 0
        
        customer = Customer.objects.first()
        
        if not all([blister_product, location, customer]):
            print("❌ No hay datos suficientes para probar stock insuficiente")
            return
        
        # Intentar vender más de lo que hay en stock
        required_quantity = current_stock + 10  # Pedir 10 más de lo disponible
        
        # Crear datos de venta
        sale_data = {
            'customer': customer.id,
            'location': location.id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': blister_product.id,
                    'quantity': required_quantity,
                    'unit_price': '5000.00'
                }
            ]
        }
        
        print(f"Stock actual de {blister_product.name}: {current_stock}")
        print(f"Intentando vender {required_quantity} unidades (tenemos {current_stock})")
        
        # Crear serializer y validar
        serializer = SaleSerializer(data=sale_data)
        if not serializer.is_valid():
            print("✅ Validación falló como esperado:")
            errors = serializer.errors
            
            # Buscar errores de stock insuficiente
            for key, value in errors.items():
                if 'items' in key and isinstance(value, dict):
                    if 'suggestions' in str(value):
                        print(f"✅ Sugerencias encontradas en error: {key}")
                        print(f"   Detalles: {json.dumps(value, indent=2, default=str)}")
                    else:
                        print(f"⚠️  Error sin sugerencias: {value}")
        else:
            print("❌ La validación no falló (esto es inesperado)")
            
    except Exception as e:
        print(f"❌ Error en la prueba: {e}")

def test_conversion_execution():
    """Testa la ejecución de una conversión manual."""
    print("\n=== ⚡ TEST: EJECUCIÓN DE CONVERSIÓN ===")
    
    try:
        # Buscar una conversión disponible
        conversion = ProductConversion.objects.first()
        location = Location.objects.first()
        user = User.objects.first()
        
        if not all([conversion, location]):
            print("❌ No hay conversiones o ubicaciones disponibles")
            return
        
        # Verificar stock antes
        from_stock_before = InventoryStock.get_total_stock(conversion.from_product, location)
        to_stock_before = InventoryStock.get_total_stock(conversion.to_product, location)
        
        print(f"ANTES - {conversion.from_product.name}: {from_stock_before}")
        print(f"ANTES - {conversion.to_product.name}: {to_stock_before}")
        
        if from_stock_before > 0:
            # Verificar si el producto requiere control de lotes
            batch_to_use = None
            if conversion.from_product.requires_batch_control:
                # Buscar un lote con stock disponible
                stock_with_batch = InventoryStock.objects.filter(
                    product=conversion.from_product,
                    location=location,
                    batch__isnull=False,
                    quantity__gt=0
                ).first()
                
                if stock_with_batch:
                    batch_to_use = stock_with_batch.batch
                    print(f"Usando lote: {batch_to_use.batch_number} (vence: {batch_to_use.expiry_date})")
                else:
                    print(f"❌ Producto {conversion.from_product.name} requiere lote pero no hay lotes con stock disponible")
                    return
            
            # Ejecutar conversión directamente (sin usar API)
            quantity_to_convert = 1
            print(f"\nEjecutando conversión: {quantity_to_convert} {conversion.from_product.name}")
            
            result = conversion.execute_conversion(
                quantity_to_convert=quantity_to_convert,
                location=location,
                batch=batch_to_use,
                user=user
            )
            
            print("✅ Conversión ejecutada exitosamente:")
            print(f"   Resultado: {result}")
            
            # Verificar stock después
            from_stock_after = InventoryStock.get_total_stock(conversion.from_product, location)
            to_stock_after = InventoryStock.get_total_stock(conversion.to_product, location)
            
            print(f"\nDESPUÉS - {conversion.from_product.name}: {from_stock_after}")
            print(f"DESPUÉS - {conversion.to_product.name}: {to_stock_after}")
            
            # Verificar que la conversión fue correcta
            expected_decrease = quantity_to_convert
            expected_increase = quantity_to_convert * conversion.conversion_rate
            
            actual_decrease = from_stock_before - from_stock_after
            actual_increase = to_stock_after - to_stock_before
            
            print(f"\n📊 VALIDACIÓN:")
            print(f"   Disminución esperada: {expected_decrease}, actual: {actual_decrease}")
            print(f"   Aumento esperado: {expected_increase}, actual: {actual_increase}")
            
            if actual_decrease == expected_decrease and actual_increase == expected_increase:
                print("✅ Conversión validada correctamente")
            else:
                print("❌ Los números de conversión no coinciden")
                
        else:
            print(f"❌ No hay stock disponible de {conversion.from_product.name} para convertir")
            
    except Exception as e:
        print(f"❌ Error ejecutando conversión: {e}")

def run_all_tests():
    """Ejecuta todos los tests del sistema."""
    print("🧪 INICIANDO TESTS DEL SISTEMA DE PRODUCTOS INDEPENDIENTES")
    print("=" * 60)
    
    test_system_status()
    test_conversion_suggestions() 
    test_insufficient_stock_scenario()
    test_conversion_execution()
    
    print("\n" + "=" * 60)
    print("🎉 TESTS COMPLETADOS")

if __name__ == "__main__":
    run_all_tests() 
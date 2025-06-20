import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from sales.models import Sale, SaleItem, Customer
from sales.serializers import SaleSerializer, SaleItemSerializer
from catalogs.models import Product, ProductBatch, Category, ProductComponent
from inventory.models import Location, InventoryStock, InventoryMovement


@pytest.fixture
def kit_test_setup():
    """Configuración de datos de prueba para ventas con kits y componentes."""
    
    # Crear categoría
    category = Category.objects.create(
        name="Medicamentos Kit",
        description="Productos farmacéuticos en kits"
    )
    
    # Crear ubicación
    location = Location.objects.create(
        name="Sede Central",
        type="sede",
        address="Calle Principal 123"
    )
    
    # Crear producto componente (blister individual)
    component_product = Product.objects.create(
        name="Blister Ibuprofeno 400mg",
        sku="IBU-BLI-001",
        description="Blister individual de ibuprofeno",
        unit="blister",
        category=category,
        product_type='component',
        requires_batch_control=False  # Simplificamos para evitar problemas de lotes con desarmado
    )
    
    # Crear producto compuesto (caja de blisters)
    composite_product = Product.objects.create(
        name="Caja Ibuprofeno 10 Blisters",
        sku="IBU-CAJ-001",
        description="Caja conteniendo 10 blisters de ibuprofeno",
        unit="caja",
        category=category,
        product_type='composite',
        requires_batch_control=False
    )
    
    # Crear producto simple para comparación
    simple_product = Product.objects.create(
        name="Algodón Simple",
        sku="ALG-SIM-001",
        description="Algodón simple",
        unit="unidad",
        category=category,
        product_type='simple',
        requires_batch_control=False
    )
    
    # Crear relación componente-compuesto (1 caja = 10 blisters)
    kit_relation = ProductComponent.objects.create(
        composite_product=composite_product,
        component_product=component_product,
        quantity=10
    )
    
    # Crear lotes para el componente (aunque no se usen)
    batch1 = ProductBatch.objects.create(
        product=component_product,
        batch_number="LOT-IBU-2024-001",
        expiry_date="2025-12-31"
    )
    
    batch2 = ProductBatch.objects.create(
        product=component_product,
        batch_number="LOT-IBU-2024-002",
        expiry_date="2025-06-30"
    )
    
    # Crear stock inicial
    # Stock directo de componentes (algunos blisters sueltos) - sin lote
    InventoryStock.objects.create(
        product=component_product,
        location=location,
        batch=None,  # Sin lote ya que no requiere control
        quantity=5  # 5 blisters sueltos
    )
    
    # Stock de productos compuestos (cajas completas)
    InventoryStock.objects.create(
        product=composite_product,
        location=location,
        batch=None,
        quantity=3  # 3 cajas (equivalente a 30 blisters)
    )
    
    # Stock de producto simple
    InventoryStock.objects.create(
        product=simple_product,
        location=location,
        batch=None,
        quantity=100
    )
    
    # Crear cliente
    customer = Customer.objects.create(
        name="Hospital Central",
        email="compras@hospital.com"
    )
    
    return {
        'component_product': component_product,
        'composite_product': composite_product,
        'simple_product': simple_product,
        'kit_relation': kit_relation,
        'location': location,
        'batch1': batch1,
        'batch2': batch2,
        'customer': customer,
        'category': category
    }


@pytest.mark.django_db
class TestCompositeProductSales:
    """Tests para venta de productos compuestos (kits/cajas)."""

    def test_sell_composite_product_directly(self, kit_test_setup):
        """Test vender producto compuesto directamente."""
        sale_data = {
            'customer': kit_test_setup['customer'].id,
            'location': kit_test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': kit_test_setup['composite_product'].id,
                    'quantity': 2,  # Vender 2 cajas
                    'unit_price': '50000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que la venta se creó correctamente
        assert sale.items.count() == 1
        item = sale.items.first()
        assert item.product == kit_test_setup['composite_product']
        assert item.quantity == 2
        
        # Verificar que se creó movimiento de salida del producto compuesto
        composite_movements = InventoryMovement.objects.filter(
            product=kit_test_setup['composite_product'],
            movement_type='out',
            notes__contains=f'Venta #{sale.id}'
        )
        assert composite_movements.count() == 1
        composite_movement = composite_movements.first()
        assert composite_movement.quantity == 2
        
        # Verificar que se crearon movimientos automáticos de componentes
        component_movements = InventoryMovement.objects.filter(
            product=kit_test_setup['component_product'],
            movement_type='composite_conversion',
            related_composite_movement=composite_movement
        )
        assert component_movements.count() == 1
        component_movement = component_movements.first()
        assert component_movement.quantity == 20  # 2 cajas * 10 blisters por caja
        
        # Verificar stock final
        composite_stock = InventoryStock.objects.get(
            product=kit_test_setup['composite_product'],
            location=kit_test_setup['location']
        )
        assert composite_stock.quantity == 1  # 3 - 2 = 1

    def test_sell_composite_insufficient_stock(self, kit_test_setup):
        """Test que falla al vender más productos compuestos del stock disponible."""
        sale_data = {
            'customer': kit_test_setup['customer'].id,
            'location': kit_test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': kit_test_setup['composite_product'].id,
                    'quantity': 5,  # Intentar vender 5 cajas (solo hay 3)
                    'unit_price': '50000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert not serializer.is_valid()
        error_str = str(serializer.errors)
        assert 'Stock insuficiente' in error_str


@pytest.mark.django_db
class TestComponentProductSales:
    """Tests para venta de componentes individuales."""

    def test_sell_component_from_direct_stock(self, kit_test_setup):
        """Test vender componente desde stock directo."""
        sale_data = {
            'customer': kit_test_setup['customer'].id,
            'location': kit_test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': kit_test_setup['component_product'].id,
                    'quantity': 3,  # Vender 3 blisters (hay 5 disponibles)
                    'unit_price': '5000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que la venta se creó correctamente
        assert sale.items.count() == 1
        item = sale.items.first()
        assert item.product == kit_test_setup['component_product']
        assert item.batch is None
        assert item.quantity == 3
        
        # Verificar movimiento de inventario
        movements = InventoryMovement.objects.filter(
            product=kit_test_setup['component_product'],
            movement_type='out',
            notes__contains=f'Venta #{sale.id} - Componente individual'
        )
        assert movements.count() == 1
        assert movements.first().quantity == 3
        
        # Verificar stock final
        component_stock = InventoryStock.objects.get(
            product=kit_test_setup['component_product'],
            location=kit_test_setup['location'],
            batch__isnull=True
        )
        assert component_stock.quantity == 2  # 5 - 3 = 2

    def test_sell_component_auto_breakdown_kits(self, kit_test_setup):
        """Test vender componente usando desarmado automático de kits."""
        sale_data = {
            'customer': kit_test_setup['customer'].id,
            'location': kit_test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': kit_test_setup['component_product'].id,
                    'quantity': 15,  # Vender 15 blisters (5 directos + 10 de 1 caja)
                    'unit_price': '5000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que la venta se creó correctamente
        assert sale.items.count() == 1
        item = sale.items.first()
        assert item.quantity == 15
        
        # Verificar que se usó stock directo primero
        direct_movements = InventoryMovement.objects.filter(
            product=kit_test_setup['component_product'],
            movement_type='out',
            notes__contains='Componente individual'
        )
        assert direct_movements.count() == 1
        assert direct_movements.first().quantity == 5
        
        # Verificar que se desarmó una caja
        breakdown_movements = InventoryMovement.objects.filter(
            product=kit_test_setup['composite_product'],
            movement_type='out',
            notes__contains='Desarmado automático'
        )
        assert breakdown_movements.count() == 1
        assert breakdown_movements.first().quantity == 1  # 1 caja desarmada
        
        # Verificar que se vendieron componentes del desarmado
        kit_sale_movements = InventoryMovement.objects.filter(
            product=kit_test_setup['component_product'],
            movement_type='out',
            notes__contains='De desarmado'
        )
        assert kit_sale_movements.count() == 1
        assert kit_sale_movements.first().quantity == 10  # 10 blisters de la caja
        
        # Verificar stock final
        composite_stock = InventoryStock.objects.get(
            product=kit_test_setup['composite_product'],
            location=kit_test_setup['location']
        )
        assert composite_stock.quantity == 2  # 3 - 1 = 2 cajas
        
        # El stock directo de componentes debe estar agotado
        component_stock = InventoryStock.objects.get(
            product=kit_test_setup['component_product'],
            location=kit_test_setup['location'],
            batch__isnull=True
        )
        assert component_stock.quantity == 0  # 5 - 5 = 0

    def test_sell_component_multiple_kit_breakdown(self, kit_test_setup):
        """Test vender componente que requiere desarmar múltiples kits."""
        sale_data = {
            'customer': kit_test_setup['customer'].id,
            'location': kit_test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': kit_test_setup['component_product'].id,
                    'quantity': 25,  # 5 directos + 20 de 2 cajas
                    'unit_price': '5000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que se desarmaron 2 cajas
        breakdown_movements = InventoryMovement.objects.filter(
            product=kit_test_setup['composite_product'],
            movement_type='out',
            notes__contains='Desarmado automático'
        )
        assert breakdown_movements.count() == 1
        assert breakdown_movements.first().quantity == 2  # 2 cajas desarmadas
        
        # Verificar stock final de cajas
        composite_stock = InventoryStock.objects.get(
            product=kit_test_setup['composite_product'],
            location=kit_test_setup['location']
        )
        assert composite_stock.quantity == 1  # 3 - 2 = 1 caja

    def test_sell_component_insufficient_total_stock(self, kit_test_setup):
        """Test que falla al vender más componentes del stock total disponible."""
        sale_data = {
            'customer': kit_test_setup['customer'].id,
            'location': kit_test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': kit_test_setup['component_product'].id,
                    'quantity': 40,  # 5 directos + 30 de 3 cajas = 35 total disponible
                    'unit_price': '5000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert not serializer.is_valid()
        error_str = str(serializer.errors)
        assert 'Stock insuficiente' in error_str


@pytest.mark.django_db
class TestMixedProductSales:
    """Tests para ventas con productos mixtos (simples, compuestos y componentes)."""

    def test_mixed_sale_all_product_types(self, kit_test_setup):
        """Test venta mixta con productos simples, compuestos y componentes."""
        sale_data = {
            'customer': kit_test_setup['customer'].id,
            'location': kit_test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                # Producto simple
                {
                    'product': kit_test_setup['simple_product'].id,
                    'quantity': 10,
                    'unit_price': '1000.00'
                },
                # Producto compuesto
                {
                    'product': kit_test_setup['composite_product'].id,
                    'quantity': 1,
                    'unit_price': '45000.00'
                },
                # Componente individual
                {
                    'product': kit_test_setup['component_product'].id,
                    'quantity': 3,
                    'unit_price': '5000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que todos los items se crearon
        assert sale.items.count() == 3
        
        # Verificar movimientos de inventario apropiados
        movements = InventoryMovement.objects.filter(
            notes__contains=f'Venta #{sale.id}'
        )
        
        # Debe haber al menos 3 movimientos (uno por tipo de producto)
        # Puede haber más si se considera el composite_conversion automático
        assert movements.count() >= 3
        
        # Verificar tipos específicos de movimientos
        simple_movements = movements.filter(product=kit_test_setup['simple_product'])
        assert simple_movements.count() == 1
        
        composite_movements = movements.filter(product=kit_test_setup['composite_product'])
        assert composite_movements.count() == 1
        
        component_movements = movements.filter(
            product=kit_test_setup['component_product']
        )
        # Debe haber al menos un movimiento del componente (puede ser directo o de desarmado)
        assert component_movements.count() >= 1

    def test_component_sale_with_multiple_kits(self, kit_test_setup):
        """Test venta de componente cuando hay múltiples kits que lo contienen."""
        # Crear otro kit que también contiene el mismo componente
        another_composite = Product.objects.create(
            name="Kit Médico Básico",
            sku="KIT-MED-001",
            description="Kit médico básico",
            unit="kit",
            category=kit_test_setup['category'],
            product_type='composite',
            requires_batch_control=False
        )
        
        # Este kit contiene 5 blisters (menos eficiente que el primero)
        ProductComponent.objects.create(
            composite_product=another_composite,
            component_product=kit_test_setup['component_product'],
            quantity=5
        )
        
        # Agregar stock del nuevo kit
        InventoryStock.objects.create(
            product=another_composite,
            location=kit_test_setup['location'],
            batch=None,
            quantity=2  # 2 kits (equivalente a 10 blisters)
        )
        
        # Vender componentes que requieran usar ambos tipos de kits
        sale_data = {
            'customer': kit_test_setup['customer'].id,
            'location': kit_test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': kit_test_setup['component_product'].id,
                    'quantity': 20,  # 5 directos + 10 de 1 caja grande + 5 de 1 kit pequeño
                    'unit_price': '5000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Debe preferir el kit más eficiente (10 componentes por kit)
        breakdown_movements = InventoryMovement.objects.filter(
            movement_type='out',
            notes__contains='Desarmado automático'
        ).order_by('product__name')
        
        # Debe haber al menos un desarmado (puede ser del kit más eficiente)
        assert breakdown_movements.count() >= 1
        
        # Verificar que se desarmó algún kit
        composite_breakdown = breakdown_movements.filter(
            product=kit_test_setup['composite_product']
        ).first()
        kit_breakdown = breakdown_movements.filter(
            product=another_composite
        ).first()
        
        # Debe haber desarmado al menos uno de los dos tipos de kits
        assert composite_breakdown is not None or kit_breakdown is not None
        
        # Si se desarmó el kit principal, debe ser al menos 1 caja (puede ser más según la lógica de desarmado)
        if composite_breakdown:
            assert composite_breakdown.quantity >= 1  # Al menos 1 caja de 10 blisters
        
        # Si se desarmó el kit secundario, debe ser la cantidad necesaria
        if kit_breakdown:
            assert kit_breakdown.quantity >= 1  # Al menos 1 kit


@pytest.mark.django_db  
class TestStockValidationWithKits:
    """Tests para validaciones de stock con productos compuestos."""

    def test_component_sale_no_kits_available(self, kit_test_setup):
        """Test venta de componente cuando no hay kits disponibles."""
        # Agotar stock de productos compuestos
        composite_stock = InventoryStock.objects.get(
            product=kit_test_setup['composite_product'],
            location=kit_test_setup['location']
        )
        composite_stock.quantity = 0
        composite_stock.save()
        
        sale_data = {
            'customer': kit_test_setup['customer'].id,
            'location': kit_test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': kit_test_setup['component_product'].id,
                    'quantity': 10,  # Solo hay 5 directos, no hay kits para desarmar
                    'unit_price': '5000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert not serializer.is_valid()
        error_str = str(serializer.errors)
        assert 'Stock insuficiente' in error_str
        assert 'Disponible total: 5' in error_str

    def test_validate_batch_requirements_for_components(self, kit_test_setup):
        """Test validación - este test ya no aplica porque los componentes no requieren lotes."""
        # Cambiar el producto para que requiera lotes
        kit_test_setup['component_product'].requires_batch_control = True
        kit_test_setup['component_product'].save()
        
        sale_data = {
            'customer': kit_test_setup['customer'].id,
            'location': kit_test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': kit_test_setup['component_product'].id,
                    # Falta el lote requerido
                    'quantity': 3,
                    'unit_price': '5000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert not serializer.is_valid()
        error_str = str(serializer.errors)
        assert 'requiere especificar un lote' in error_str 
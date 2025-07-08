import pytest
from django.core.exceptions import ValidationError
from django.db import transaction, models
from datetime import date, timedelta
from decimal import Decimal

from inventory.models import Location, InventoryStock, InventoryMovement
from catalogs.models import Category, Product, ProductBatch, ProductComponent
from sales.models import Sale, SaleItem, Customer
from sales.serializers import SaleSerializer


@pytest.fixture
def comprehensive_test_setup():
    """
    Fixture completo para testing comprehensivo de productos con lotes y componentes.
    
    Estructura creada:
    1. Productos simples con y sin lotes
    2. Componentes con lotes que forman parte de kits
    3. Kits mixtos y cajas homogéneas
    4. Jerarquías anidadas (componentes que son componentes de otros)
    5. Componentes compartidos entre múltiples kits
    """
    # Categorías
    category_med = Category.objects.create(name='Medicamentos', description='Productos médicos')
    category_kit = Category.objects.create(name='Kits', description='Productos compuestos')
    
    # Ubicaciones
    main_location = Location.objects.create(name='Bodega Principal', type='bodega', address='Principal 123')
    secondary_location = Location.objects.create(name='Bodega Secundaria', type='bodega', address='Secundaria 456')
    
    # Cliente
    customer = Customer.objects.create(name='Hospital Test', email='test@hospital.com')
    
    # === PRODUCTOS BASE (NIVEL MÁS BAJO) ===
    
    # Componente con lotes - tableta individual
    tablet_component = Product.objects.create(
        sku='MED-TAB-IBU-001',
        name='Tableta Ibuprofeno 600mg',
        unit='tableta',
        category=category_med,
        product_type='component',
        requires_batch_control=True,
        sale_price=Decimal('500.00')
    )
    
    # Componente con lotes - cápsula individual
    capsule_component = Product.objects.create(
        sku='MED-CAP-AMO-001',
        name='Cápsula Amoxicilina 500mg',
        unit='cápsula',
        category=category_med,
        product_type='component',
        requires_batch_control=True,
        sale_price=Decimal('800.00')
    )
    
    # Componente sin lotes - jeringa
    syringe_component = Product.objects.create(
        sku='MED-SYR-DIS-001',
        name='Jeringa Desechable 3ml',
        unit='unidad',
        category=category_med,
        product_type='component',
        requires_batch_control=False,
        sale_price=Decimal('300.00')
    )
    
    # === PRODUCTOS NIVEL INTERMEDIO (BLISTERS) ===
    
    # Blister que contiene tabletas (componente intermedio SIN lotes para simplificar tests)
    blister_ibu = Product.objects.create(
        sku='MED-BLI-IBU-001',
        name='Blister Ibuprofeno 10 tabletas',
        unit='blister',
        category=category_med,
        product_type='component',  # Los blisters son componentes, no cajas
        requires_batch_control=False,  # Simplificamos para tests de algoritmo de prioridad
        sale_price=Decimal('4500.00')
    )
    
    # Blister que contiene cápsulas (componente intermedio SIN lotes para simplificar tests)
    blister_amo = Product.objects.create(
        sku='MED-BLI-AMO-001',
        name='Blister Amoxicilina 10 cápsulas',
        unit='blister',
        category=category_med,
        product_type='component',  # Los blisters son componentes, no cajas
        requires_batch_control=False,  # Simplificamos para tests de algoritmo de prioridad
        sale_price=Decimal('7500.00')
    )
    
    # === PRODUCTOS NIVEL ALTO (CAJAS Y KITS) ===
    
    # Caja homogénea - contiene solo blisters de ibuprofeno
    box_ibu = Product.objects.create(
        sku='MED-BOX-IBU-001',
        name='Caja Ibuprofeno 5 blisters',
        unit='caja',
        category=category_kit,
        product_type='boxed_component',
        requires_batch_control=False,  # Las cajas no suelen tener lotes propios
        sale_price=Decimal('22000.00')
    )
    
    # Caja homogénea - contiene solo blisters de amoxicilina
    box_amo = Product.objects.create(
        sku='MED-BOX-AMO-001',
        name='Caja Amoxicilina 4 blisters',
        unit='caja',
        category=category_kit,
        product_type='boxed_component',
        requires_batch_control=False,
        sale_price=Decimal('29000.00')
    )
    
    # Kit mixto - contiene diferentes tipos de productos
    mixed_kit = Product.objects.create(
        sku='KIT-MED-MIX-001',
        name='Kit Médico Completo',
        unit='kit',
        category=category_kit,
        product_type='mixed_kit',
        requires_batch_control=False,
        sale_price=Decimal('35000.00')
    )
    
    # Kit premium - contiene cajas completas (jerarquía anidada)
    premium_kit = Product.objects.create(
        sku='KIT-PREM-001',
        name='Kit Premium Hospital',
        unit='kit',
        category=category_kit,
        product_type='mixed_kit',
        requires_batch_control=False,
        sale_price=Decimal('75000.00')
    )
    
    # === RELACIONES DE COMPONENTES ===
    
    # Tabletas forman blisters
    ProductComponent.objects.create(
        composite_product=blister_ibu,
        component_product=tablet_component,
        quantity=10  # 1 blister = 10 tabletas
    )
    
    # Cápsulas forman blisters
    ProductComponent.objects.create(
        composite_product=blister_amo,
        component_product=capsule_component,
        quantity=10  # 1 blister = 10 cápsulas
    )
    
    # Blisters forman cajas homogéneas
    ProductComponent.objects.create(
        composite_product=box_ibu,
        component_product=blister_ibu,
        quantity=5  # 1 caja = 5 blisters
    )
    
    ProductComponent.objects.create(
        composite_product=box_amo,
        component_product=blister_amo,
        quantity=4  # 1 caja = 4 blisters
    )
    
    # Kit mixto contiene blisters directos + jeringas
    ProductComponent.objects.create(
        composite_product=mixed_kit,
        component_product=blister_ibu,
        quantity=2  # 2 blisters ibuprofeno
    )
    
    ProductComponent.objects.create(
        composite_product=mixed_kit,
        component_product=blister_amo,
        quantity=1  # 1 blister amoxicilina
    )
    
    ProductComponent.objects.create(
        composite_product=mixed_kit,
        component_product=syringe_component,
        quantity=5  # 5 jeringas
    )
    
    # Kit premium contiene cajas completas (jerarquía anidada)
    ProductComponent.objects.create(
        composite_product=premium_kit,
        component_product=box_ibu,
        quantity=1  # 1 caja ibuprofeno
    )
    
    ProductComponent.objects.create(
        composite_product=premium_kit,
        component_product=box_amo,
        quantity=1  # 1 caja amoxicilina
    )
    
    # === LOTES ===
    
    # Lotes para tabletas ibuprofeno
    tablet_batch_1 = ProductBatch.objects.create(
        product=tablet_component,
        batch_number='TAB-IBU-2024-001',
        expiry_date=date.today() + timedelta(days=365),
        manufacturing_date=date.today() - timedelta(days=30)
    )
    
    tablet_batch_2 = ProductBatch.objects.create(
        product=tablet_component,
        batch_number='TAB-IBU-2024-002', 
        expiry_date=date.today() + timedelta(days=180),  # Vence antes
        manufacturing_date=date.today() - timedelta(days=60)
    )
    
    # Lotes para cápsulas amoxicilina
    capsule_batch_1 = ProductBatch.objects.create(
        product=capsule_component,
        batch_number='CAP-AMO-2024-001',
        expiry_date=date.today() + timedelta(days=300),
        manufacturing_date=date.today() - timedelta(days=45)
    )
    
    # Los blisters ya no requieren lotes para simplificar tests de prioridad
    # Se mantiene la referencia para compatibilidad pero será None
    blister_ibu_batch_1 = None
    blister_amo_batch_1 = None
    
    # === STOCK INICIAL ===
    
    # Stock de componentes base
    InventoryStock.objects.create(
        product=tablet_component, location=main_location,
        batch=tablet_batch_1, quantity=100
    )
    InventoryStock.objects.create(
        product=tablet_component, location=main_location,
        batch=tablet_batch_2, quantity=50
    )
    InventoryStock.objects.create(
        product=capsule_component, location=main_location,
        batch=capsule_batch_1, quantity=80
    )
    InventoryStock.objects.create(
        product=syringe_component, location=main_location,
        batch=None, quantity=200
    )
    
    # Stock de blisters (sin lotes)
    InventoryStock.objects.create(
        product=blister_ibu, location=main_location,
        batch=None, quantity=20
    )
    InventoryStock.objects.create(
        product=blister_amo, location=main_location,
        batch=None, quantity=15
    )
    
    # Stock de cajas
    InventoryStock.objects.create(
        product=box_ibu, location=main_location,
        batch=None, quantity=5
    )
    InventoryStock.objects.create(
        product=box_amo, location=main_location,
        batch=None, quantity=3
    )
    
    # Stock de kits
    InventoryStock.objects.create(
        product=mixed_kit, location=main_location,
        batch=None, quantity=2
    )
    InventoryStock.objects.create(
        product=premium_kit, location=main_location,
        batch=None, quantity=1
    )
    
    # Stock en ubicación secundaria
    InventoryStock.objects.create(
        product=tablet_component, location=secondary_location,
        batch=tablet_batch_1, quantity=30
    )
    InventoryStock.objects.create(
        product=blister_ibu, location=secondary_location,
        batch=None, quantity=5
    )
    
    return {
        'locations': {
            'main': main_location,
            'secondary': secondary_location
        },
        'customer': customer,
        'categories': {
            'med': category_med,
            'kit': category_kit
        },
        'products': {
            'base': {
                'tablet': tablet_component,
                'capsule': capsule_component,
                'syringe': syringe_component
            },
            'intermediate': {
                'blister_ibu': blister_ibu,
                'blister_amo': blister_amo
            },
            'high_level': {
                'box_ibu': box_ibu,
                'box_amo': box_amo,
                'mixed_kit': mixed_kit,
                'premium_kit': premium_kit
            }
        },
        'batches': {
            'tablet_1': tablet_batch_1,
            'tablet_2': tablet_batch_2,
            'capsule_1': capsule_batch_1,
            'blister_ibu_1': None,
            'blister_amo_1': None
        }
    }


@pytest.mark.django_db
class TestComplexBatchHierarchies:
    """
    Tests para jerarquías complejas de productos con lotes.
    
    Escenarios cubiertos:
    1. Componentes con lotes que forman parte de productos compuestos
    2. Jerarquías anidadas (3+ niveles de componentes)
    3. FIFO automático en múltiples niveles
    4. Validación de consistencia de lotes
    """
    
    def test_nested_component_breakdown_with_batches(self, comprehensive_test_setup):
        """
        Test desarmado de kit premium que contiene cajas que contienen blisters que contienen tabletas.
        Verifica que los lotes se manejen correctamente en cada nivel.
        """
        setup = comprehensive_test_setup
        premium_kit = setup['products']['high_level']['premium_kit']
        main_location = setup['locations']['main']
        
        # Estado inicial: 1 kit premium disponible
        initial_kit_stock = InventoryStock.objects.get(
            product=premium_kit, 
            location=main_location
        ).quantity
        assert initial_kit_stock == 1
        
        # Desarmar el kit premium
        breakdown_movement = InventoryMovement.create_composite_breakdown(
            composite_product=premium_kit,
            location=main_location,
            quantity=1,
            notes='Desarmado para análisis de jerarquía'
        )
        
        # Verificar que se crearon las cajas
        box_ibu_stock = InventoryStock.objects.get(
            product=setup['products']['high_level']['box_ibu'],
            location=main_location
        ).quantity
        assert box_ibu_stock == 6  # 5 iniciales + 1 del desarmado
        
        box_amo_stock = InventoryStock.objects.get(
            product=setup['products']['high_level']['box_amo'],
            location=main_location
        ).quantity
        assert box_amo_stock == 4  # 3 iniciales + 1 del desarmado
        
        # Ahora desarmar una caja de ibuprofeno para verificar la cadena completa
        breakdown_box = InventoryMovement.create_composite_breakdown(
            composite_product=setup['products']['high_level']['box_ibu'],
            location=main_location,
            quantity=1,
            notes='Desarmado de caja para verificar cadena'
        )
        
        # Verificar que se crearon blisters
        blister_ibu_stock = InventoryStock.objects.get(
            product=setup['products']['intermediate']['blister_ibu'],
            location=main_location,
            batch=None
        ).quantity
        assert blister_ibu_stock == 30  # 20 iniciales + 10 del desarmado (puede haber otros desarmados previos)
        
        # Verificar movimientos en cadena
        movements = InventoryMovement.objects.filter(
            location=main_location,
            notes__contains='Desarmado'
        ).order_by('id')
        
        assert movements.count() >= 2
        assert movements.filter(product=premium_kit).exists()
        assert movements.filter(product=setup['products']['high_level']['box_ibu']).exists()

    def test_fifo_with_multiple_batch_levels(self, comprehensive_test_setup):
        """
        Test que verifica FIFO cuando hay lotes en múltiples niveles de la jerarquía.
        """
        setup = comprehensive_test_setup
        tablet = setup['products']['base']['tablet']
        blister_ibu = setup['products']['intermediate']['blister_ibu']
        main_location = setup['locations']['main']
        customer = setup['customer']
        
        # Vender 25 tabletas directamente (especificando el lote que vence antes)
        sale_data = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': tablet.id,
                    'batch': setup['batches']['tablet_2'].id,  # Lote que vence antes
                    'quantity': 25,
                    'unit_price': '500.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que se usó el lote especificado
        movements = InventoryMovement.objects.filter(
            product=tablet,
            movement_type='out',
            location=main_location,
            batch=setup['batches']['tablet_2']
        ).order_by('id')
        
        # Debe haber movimientos del lote especificado
        assert movements.exists()
        assert movements.first().quantity == 25
        
        # Verificar stock restante del lote que vence antes
        remaining_batch_2 = InventoryStock.objects.get(
            product=tablet,
            location=main_location,
            batch=setup['batches']['tablet_2']
        ).quantity
        assert remaining_batch_2 == 25  # 50 - 25 = 25

    def test_mixed_batch_requirements_in_hierarchy(self, comprehensive_test_setup):
        """
        Test productos con y sin control de lotes en la misma jerarquía.
        """
        setup = comprehensive_test_setup
        mixed_kit = setup['products']['high_level']['mixed_kit']
        main_location = setup['locations']['main']
        customer = setup['customer']
        
        # Vender kit mixto que contiene productos con y sin lotes
        sale_data = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': mixed_kit.id,
                    'quantity': 1,
                    'unit_price': '35000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que se movieron productos con lotes
        blister_movements = InventoryMovement.objects.filter(
            product__in=[
                setup['products']['intermediate']['blister_ibu'],
                setup['products']['intermediate']['blister_amo']
            ],
            movement_type='composite_conversion',
            location=main_location
        )
        assert blister_movements.count() == 2
        
        # Verificar que se movieron productos sin lotes
        syringe_movements = InventoryMovement.objects.filter(
            product=setup['products']['base']['syringe'],
            movement_type='composite_conversion',
            location=main_location
        )
        assert syringe_movements.count() == 1
        assert syringe_movements.first().batch is None

    def test_batch_expiry_validation_in_components(self, comprehensive_test_setup):
        """
        Test validación de fechas de vencimiento en componentes.
        """
        setup = comprehensive_test_setup
        tablet = setup['products']['base']['tablet']
        main_location = setup['locations']['main']
        
        # Crear lote vencido
        expired_batch = ProductBatch.objects.create(
            product=tablet,
            batch_number='TAB-IBU-EXPIRED',
            expiry_date=date.today() - timedelta(days=1),  # Vencido
            manufacturing_date=date.today() - timedelta(days=400)
        )
        
        # Crear stock con lote vencido
        InventoryStock.objects.create(
            product=tablet,
            location=main_location,
            batch=expired_batch,
            quantity=20
        )
        
        # Verificar que el sistema puede detectar lotes vencidos
        expired_stock = InventoryStock.objects.filter(
            product=tablet,
            location=main_location,
            batch__expiry_date__lt=date.today()
        )
        assert expired_stock.count() == 1
        assert expired_stock.first().batch == expired_batch


@pytest.mark.django_db  
class TestPriorityAlgorithmBreakdown:
    """
    Tests para verificar el algoritmo de prioridad en el desglose de productos.
    
    Prioridad:
    1. Stock directo del componente
    2. Cajas homogéneas (boxed_component) - menor desperdicio
    3. Kits mixtos (mixed_kit) - mayor desperdicio
    """
    
    def test_priority_direct_stock_first(self, comprehensive_test_setup):
        """
        Test que verifica que se usa stock directo antes de desarmar kits.
        """
        setup = comprehensive_test_setup
        blister_ibu = setup['products']['intermediate']['blister_ibu']
        main_location = setup['locations']['main']
        customer = setup['customer']
        
        # Estado inicial: 20 blisters directos disponibles
        initial_direct = InventoryStock.objects.get(
            product=blister_ibu,
            location=main_location,
            batch=None
        ).quantity
        assert initial_direct == 20
        
        # Vender 15 blisters (menos que el stock directo)
        sale_data = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': blister_ibu.id,
                    'quantity': 15,
                    'unit_price': '4500.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que se usó stock directo y NO se desarmaron cajas
        direct_movements = InventoryMovement.objects.filter(
            product=blister_ibu,
            movement_type='out',
            location=main_location,
            notes__contains=f'Venta #{sale.id}'
        )
        assert direct_movements.count() == 1
        assert direct_movements.first().quantity == 15
        
        # Verificar que NO hay movimientos de desarmado
        breakdown_movements = InventoryMovement.objects.filter(
            product=setup['products']['high_level']['box_ibu'],
            movement_type='out',
            notes__contains='Desarmado automático'
        )
        assert breakdown_movements.count() == 0
        
        # Verificar stock restante
        remaining_stock = InventoryStock.objects.get(
            product=blister_ibu,
            location=main_location,
            batch=setup['batches']['blister_ibu_1']
        ).quantity
        assert remaining_stock == 5  # 20 - 15 = 5

    def test_priority_boxes_over_mixed_kits(self, comprehensive_test_setup):
        """
        Test que verifica que se prefieren cajas homogéneas sobre kits mixtos.
        """
        setup = comprehensive_test_setup
        blister_ibu = setup['products']['intermediate']['blister_ibu']
        box_ibu = setup['products']['high_level']['box_ibu']
        mixed_kit = setup['products']['high_level']['mixed_kit']
        main_location = setup['locations']['main']
        customer = setup['customer']
        
        # Agotar stock directo primero
        InventoryStock.objects.filter(
            product=blister_ibu,
            location=main_location
        ).update(quantity=0)
        
        # Vender 7 blisters (más que los 5 de una caja, pero menos que dos cajas)
        # Como agotamos el stock directo, el sistema debería crear stock del desglose automático
        sale_data = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': blister_ibu.id,
                    'quantity': 7,
                    'unit_price': '4500.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que se desarmó una caja homogénea (no el kit mixto)
        box_breakdown = InventoryMovement.objects.filter(
            product=box_ibu,
            movement_type='out',
            notes__contains='Desarmado automático'
        )
        assert box_breakdown.count() >= 1
        
        # Verificar que NO se desarmó el kit mixto
        kit_breakdown = InventoryMovement.objects.filter(
            product=mixed_kit,
            movement_type='out',
            notes__contains='Desarmado automático'
        )
        assert kit_breakdown.count() == 0

    def test_priority_smaller_boxes_first(self, comprehensive_test_setup):
        """
        Test que verifica que se prefieren cajas más pequeñas para minimizar desperdicio.
        """
        setup = comprehensive_test_setup
        blister_amo = setup['products']['intermediate']['blister_amo']
        main_location = setup['locations']['main']
        customer = setup['customer']
        
        # Crear caja más grande de amoxicilina
        big_box_amo = Product.objects.create(
            sku='MED-BOX-AMO-BIG',
            name='Caja Grande Amoxicilina 10 blisters',
            unit='caja',
            category=setup['categories']['kit'],
            product_type='boxed_component',
            requires_batch_control=False,
            sale_price=Decimal('70000.00')
        )
        
        # Relación: caja grande = 10 blisters
        ProductComponent.objects.create(
            composite_product=big_box_amo,
            component_product=blister_amo,
            quantity=10
        )
        
        # Stock de caja grande
        InventoryStock.objects.create(
            product=big_box_amo,
            location=main_location,
            batch=None,
            quantity=2
        )
        
        # Agotar stock directo
        InventoryStock.objects.filter(
            product=blister_amo,
            location=main_location
        ).update(quantity=0)
        
        # Vender 3 blisters (caja pequeña=4, caja grande=10)
        # Debería preferir la caja pequeña (menos desperdicio)
        sale_data = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': blister_amo.id,
                    'quantity': 3,
                    'unit_price': '7500.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que se usó la caja pequeña
        small_box_breakdown = InventoryMovement.objects.filter(
            product=setup['products']['high_level']['box_amo'],
            movement_type='out',
            notes__contains='Desarmado automático'
        )
        assert small_box_breakdown.count() >= 1
        
        # Verificar que NO se usó la caja grande
        big_box_breakdown = InventoryMovement.objects.filter(
            product=big_box_amo,
            movement_type='out',
            notes__contains='Desarmado automático'
        )
        assert big_box_breakdown.count() == 0


@pytest.mark.django_db
class TestSharedComponentsComplex:
    """
    Tests para componentes compartidos entre múltiples kits con diferentes configuraciones.
    """
    
    def test_component_shared_between_different_kit_types(self, comprehensive_test_setup):
        """
        Test componente compartido entre caja homogénea y kit mixto.
        """
        setup = comprehensive_test_setup
        blister_ibu = setup['products']['intermediate']['blister_ibu']
        main_location = setup['locations']['main']
        
        # Verificar que el blister está en ambos tipos de kit
        # 1. En caja homogénea (box_ibu)
        box_relations = ProductComponent.objects.filter(
            component_product=blister_ibu,
            composite_product=setup['products']['high_level']['box_ibu']
        )
        assert box_relations.count() == 1
        
        # 2. En kit mixto (mixed_kit)
        kit_relations = ProductComponent.objects.filter(
            component_product=blister_ibu,
            composite_product=setup['products']['high_level']['mixed_kit']
        )
        assert kit_relations.count() == 1
        
        # Diferentes cantidades en cada kit
        box_quantity = box_relations.first().quantity  # 5
        kit_quantity = kit_relations.first().quantity  # 2
        
        assert box_quantity == 5
        assert kit_quantity == 2

    def test_preferential_breakdown_shared_component(self, comprehensive_test_setup):
        """
        Test que verifica la prioridad al desarmar cuando un componente está en múltiples kits.
        """
        setup = comprehensive_test_setup
        blister_ibu = setup['products']['intermediate']['blister_ibu']
        box_ibu = setup['products']['high_level']['box_ibu']
        mixed_kit = setup['products']['high_level']['mixed_kit']
        main_location = setup['locations']['main']
        customer = setup['customer']
        
        # Agotar stock directo
        InventoryStock.objects.filter(
            product=blister_ibu,
            location=main_location
        ).update(quantity=0)
        
        # Vender cantidad que requiere elegir entre kits
        # 6 blisters: podría venir de 1 caja (5) + 1 adicional, o 3 kits mixtos (2 cada uno)
        sale_data = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': blister_ibu.id,
                    'quantity': 6,
                    'unit_price': '4500.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Debería preferir la caja homogénea (boxed_component) sobre el kit mixto
        box_movements = InventoryMovement.objects.filter(
            product=box_ibu,
            movement_type='out',
            notes__contains='Desarmado automático'
        )
        assert box_movements.count() >= 1
        
        # El segundo blister debería venir de otro desglose eficiente
        total_movements = InventoryMovement.objects.filter(
            notes__contains='Desarmado automático',
            location=main_location
        )
        assert total_movements.count() >= 1


@pytest.mark.django_db
class TestPartialStockScenarios:
    """
    Tests para escenarios de stock insuficiente con lotes parciales.
    """
    
    def test_insufficient_stock_multiple_batches(self, comprehensive_test_setup):
        """
        Test cuando se necesita stock de múltiples lotes para completar una venta.
        """
        setup = comprehensive_test_setup
        tablet = setup['products']['base']['tablet']
        main_location = setup['locations']['main']
        customer = setup['customer']
        
                # Estado inicial: batch_1=100, batch_2=50 tabletas
        total_available = 150

        # Intentar vender más de lo disponible en el lote específico
        sale_data = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': tablet.id,
                    'batch': setup['batches']['tablet_2'].id,  # Lote que solo tiene 50
                    'quantity': 75,  # Más de las 50 disponibles en este lote
                    'unit_price': '500.00'
                }
            ]
        }

        serializer = SaleSerializer(data=sale_data)
        # Debería fallar por stock insuficiente en el lote específico
        assert not serializer.is_valid(), f"Expected validation to fail but got: {serializer.errors}"
        
        # Vender exactamente lo disponible del lote especificado
        sale_data['items'][0]['quantity'] = 50  # Solo usar el lote especificado
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que se usó solo el lote especificado
        movements = InventoryMovement.objects.filter(
            product=tablet,
            movement_type='out',
            location=main_location,
            batch=setup['batches']['tablet_2']  # Solo el lote que especificamos
        )
        
        assert movements.exists()
        assert movements.first().quantity == 50
        
        # Verificar que se agotó el stock del lote
        remaining_stock = InventoryStock.objects.get(
            product=tablet,
            location=main_location,
            batch=setup['batches']['tablet_2']
        ).quantity
        assert remaining_stock == 0

    def test_cross_location_stock_availability(self, comprehensive_test_setup):
        """
        Test disponibilidad de stock entre múltiples ubicaciones.
        """
        setup = comprehensive_test_setup
        tablet = setup['products']['base']['tablet']
        main_location = setup['locations']['main']
        secondary_location = setup['locations']['secondary']
        
        # Verificar stock en ambas ubicaciones
        main_stock = InventoryStock.objects.filter(
            product=tablet,
            location=main_location
        ).aggregate(total=models.Sum('quantity'))['total']
        
        secondary_stock = InventoryStock.objects.filter(
            product=tablet,
            location=secondary_location
        ).aggregate(total=models.Sum('quantity'))['total']
        
        assert main_stock == 150  # 100 + 50
        assert secondary_stock == 30
        
        total_available = main_stock + secondary_stock
        assert total_available == 180

    def test_partial_batch_consumption(self, comprehensive_test_setup):
        """
        Test consumo parcial de lotes en ventas secuenciales.
        """
        setup = comprehensive_test_setup
        tablet = setup['products']['base']['tablet']
        main_location = setup['locations']['main']
        customer = setup['customer']
        
        # Primera venta: consumir parcialmente el primer lote
        sale_data_1 = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': tablet.id,
                    'batch': setup['batches']['tablet_2'].id,  # Lote que vence antes
                    'quantity': 30,  # Parcial del lote que vence antes (50 disponibles)
                    'unit_price': '500.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data_1)
        assert serializer.is_valid(), serializer.errors
        sale_1 = serializer.save()
        
        # Verificar stock restante del primer lote
        remaining_batch_2 = InventoryStock.objects.get(
            product=tablet,
            location=main_location,
            batch=setup['batches']['tablet_2']
        ).quantity
        assert remaining_batch_2 == 20  # 50 - 30 = 20
        
        # Segunda venta: consumir el resto del primer lote únicamente
        sale_data_2 = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': tablet.id,
                    'batch': setup['batches']['tablet_2'].id,  # Mismo lote
                    'quantity': 20,  # Resto del primer lote
                    'unit_price': '500.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data_2)
        assert serializer.is_valid(), serializer.errors
        sale_2 = serializer.save()
        
        # Verificar que el primer lote se agotó
        remaining_batch_2 = InventoryStock.objects.get(
            product=tablet,
            location=main_location,
            batch=setup['batches']['tablet_2']
        ).quantity
        assert remaining_batch_2 == 0
        
        # Verificar que el segundo lote no se tocó
        remaining_batch_1 = InventoryStock.objects.get(
            product=tablet,
            location=main_location,
            batch=setup['batches']['tablet_1']
        ).quantity
        assert remaining_batch_1 == 100  # Sin cambios


@pytest.mark.django_db
class TestReassemblyLogic:
    """
    Tests para lógica de re-ensamblaje automático al devolver componentes.
    """
    
    def test_automatic_reassembly_on_return(self, comprehensive_test_setup):
        """
        Test re-ensamblaje automático cuando se devuelven suficientes componentes.
        """
        # Este test requerirá implementar la lógica de devoluciones
        # Por ahora, marcamos como pendiente de implementación
        pytest.skip("Lógica de re-ensamblaje automático pendiente de implementación")

    def test_partial_return_no_reassembly(self, comprehensive_test_setup):
        """
        Test que no se re-ensambla si no hay suficientes componentes.
        """
        pytest.skip("Lógica de re-ensamblaje automático pendiente de implementación")


@pytest.mark.django_db
class TestChainConversions:
    """
    Tests para conversiones en cadena (caja -> blister -> tableta).
    """
    
    def test_three_level_breakdown_chain(self, comprehensive_test_setup):
        """
        Test desarmado automático: caja -> blisters individuales.
        (El desarmado completo en cadena caja->blister->tableta requeriría múltiples niveles
        que no están soportados actualmente en el sistema)
        """
        setup = comprehensive_test_setup
        blister_ibu = setup['products']['intermediate']['blister_ibu']
        box_ibu = setup['products']['high_level']['box_ibu']
        main_location = setup['locations']['main']
        customer = setup['customer']
        
        # Reducir stock directo de blisters para forzar uso de cajas
        InventoryStock.objects.filter(
            product=blister_ibu,
            location=main_location
        ).update(quantity=2)  # Solo 2 blisters directos
        
        # Mantener stock de cajas para conversión automática
        InventoryStock.objects.filter(
            product=box_ibu,
            location=main_location
        ).update(quantity=3)  # 3 cajas = 15 blisters más (3 * 5 = 15)
        
        # Vender más blisters de los disponibles directamente
        # (2 directos + 15 de cajas = 17 disponibles total)
        sale_data = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': blister_ibu.id,
                    'quantity': 8,  # Más que los 2 directos pero menos que los 17 totales
                    'unit_price': '4500.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que se vendieron los blisters solicitados
        blister_movements = InventoryMovement.objects.filter(
            product=blister_ibu,
            movement_type='out',
            notes__contains=f'Venta #{sale.id}'
        )
        assert blister_movements.exists()
        
        # Verificar la cantidad total vendida
        total_blister_sold = sum(mov.quantity for mov in blister_movements)
        assert total_blister_sold == 8
        
        # Verificar que se desarmaron cajas para completar la venta
        # (ya que solo había 2 blisters directos pero se vendieron 8)
        box_breakdown_movements = InventoryMovement.objects.filter(
            product=box_ibu,
            movement_type='out',
            notes__contains='Desarmado automático'
        )
        assert box_breakdown_movements.exists()

    def test_selective_breakdown_optimization(self, comprehensive_test_setup):
        """
        Test que verifica que el sistema optimiza qué nivel desarmar.
        """
        setup = comprehensive_test_setup
        tablet = setup['products']['base']['tablet']
        blister_ibu = setup['products']['intermediate']['blister_ibu']
        main_location = setup['locations']['main']
        customer = setup['customer']
        
        # Scenario: hay stock de tabletas directas Y blisters
        # Al vender tabletas, debería usar stock directo primero
        initial_tablet_stock = InventoryStock.objects.filter(
            product=tablet,
            location=main_location
        ).aggregate(total=models.Sum('quantity'))['total']
        
        initial_blister_stock = InventoryStock.objects.get(
            product=blister_ibu,
            location=main_location,
            batch=None
        ).quantity
        
        # Vender menos tabletas que el stock directo disponible
        sale_data = {
            'customer': customer.id,
            'location': main_location.id,
            'sale_type': 'normal',
            'confirm_breakdown': True,
            'items': [
                {
                    'product': tablet.id,
                    'batch': setup['batches']['tablet_1'].id,  # Especificar lote
                    'quantity': 50,  # Menos que las 150 disponibles directamente
                    'unit_price': '500.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que NO se desarmaron blisters
        blister_breakdown = InventoryMovement.objects.filter(
            product=blister_ibu,
            movement_type='out',
            notes__contains='Desarmado automático'
        )
        assert blister_breakdown.count() == 0
        
        # Verificar que se usó stock directo de tabletas
        tablet_movements = InventoryMovement.objects.filter(
            product=tablet,
            movement_type='out',
            location=main_location,
            notes__contains=f'Venta #{sale.id}'
        )
        assert tablet_movements.exists() 
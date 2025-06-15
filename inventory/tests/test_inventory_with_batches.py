import pytest
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from decimal import Decimal

from inventory.models import Location, InventoryStock, InventoryMovement
from catalogs.models import Category, Product, ProductBatch, ProductComponent


@pytest.fixture
def test_setup():
    """Fixture completo para tests de inventario con lotes."""
    # Crear categoría
    category = Category.objects.create(
        name='Medicamentos Test',
        description='Categoría para tests de inventario con lotes'
    )
    
    # Crear ubicación
    location = Location.objects.create(
        name='Bodega Central Test',
        type='bodega',
        address='Calle 123'
    )
    
    # Producto que requiere control de lotes
    batch_product = Product.objects.create(
        sku='MED-ANE-LID-001',
        name='Anestesia Lidocaína',
        unit='ampolla',
        category=category,
        requires_batch_control=True
    )
    
    # Producto que NO requiere control de lotes
    no_batch_product = Product.objects.create(
        sku='EQU-FOR-ESP-001',
        name='Fórceps Espátula',
        unit='unidad',
        category=category,
        requires_batch_control=False
    )
    
    # Producto compuesto (caja)
    composite_product = Product.objects.create(
        sku='MED-CAJ-IBU-001',
        name='Caja de Ibuprofeno',
        unit='caja',
        category=category,
        product_type='composite'
    )
    
    # Producto componente (blister)
    component_product = Product.objects.create(
        sku='MED-BLI-IBU-001',
        name='Blister Ibuprofeno',
        unit='blister',
        category=category,
        product_type='component'
    )
    
    # Crear relación compuesto-componente
    ProductComponent.objects.create(
        composite_product=composite_product,
        component_product=component_product,
        quantity=10  # 1 caja = 10 blisters
    )
    
    # Crear lotes
    batch1 = ProductBatch.objects.create(
        product=batch_product,
        batch_number='LOT2024001',
        expiry_date=date(2026, 1, 15)
    )
    
    batch2 = ProductBatch.objects.create(
        product=batch_product,
        batch_number='LOT2024002',
        expiry_date=date(2025, 6, 15)  # Vence antes
    )
    
    return {
        'category': category,
        'location': location,
        'batch_product': batch_product,
        'no_batch_product': no_batch_product,
        'composite_product': composite_product,
        'component_product': component_product,
        'batch1': batch1,
        'batch2': batch2
    }


@pytest.mark.django_db
class TestInventoryStockWithBatches:
    """Tests para InventoryStock con sistema de lotes."""

    def test_create_stock_with_batch(self, test_setup):
        """Test crear stock con lote para producto que requiere control."""
        stock = InventoryStock.objects.create(
            product=test_setup['batch_product'],
            location=test_setup['location'],
            batch=test_setup['batch1'],
            quantity=50
        )
        
        assert stock.product == test_setup['batch_product']
        assert stock.location == test_setup['location']
        assert stock.batch == test_setup['batch1']
        assert stock.quantity == 50

    def test_create_stock_without_batch_for_no_batch_product(self, test_setup):
        """Test crear stock sin lote para producto que no requiere control."""
        stock = InventoryStock.objects.create(
            product=test_setup['no_batch_product'],
            location=test_setup['location'],
            quantity=25
        )
        
        assert stock.product == test_setup['no_batch_product']
        assert stock.batch is None
        assert stock.quantity == 25

    def test_stock_requires_batch_validation(self, test_setup):
        """Test que falla al crear stock sin lote para producto que requiere control."""
        with pytest.raises(ValidationError) as exc_info:
            stock = InventoryStock(
                product=test_setup['batch_product'],  # Requiere lote
                location=test_setup['location'],
                batch=None,  # Sin lote
                quantity=50
            )
            stock.full_clean()
        
        assert "Este producto requiere especificar un lote" in str(exc_info.value)

    def test_stock_no_batch_for_no_batch_product_validation(self, test_setup):
        """Test que falla al crear stock con lote para producto que no requiere control."""
        with pytest.raises(ValidationError) as exc_info:
            stock = InventoryStock(
                product=test_setup['no_batch_product'],  # No requiere lote
                location=test_setup['location'],
                batch=test_setup['batch1'],  # Con lote (lote de producto que requiere lotes)
                quantity=50
            )
            stock.full_clean()
        
        # El error será por batch mismatch ya que el lote pertenece a otro producto
        assert "El lote no corresponde al producto seleccionado" in str(exc_info.value)

    def test_batch_product_mismatch_validation(self, test_setup):
        """Test que falla al usar lote de producto diferente."""
        # Crear otro producto con lotes
        another_product = Product.objects.create(
            sku='MED-ANE-ART-001',
            name='Anestesia Articaína',
            unit='ampolla',
            category=test_setup['category'],
            requires_batch_control=True
        )
        
        with pytest.raises(ValidationError) as exc_info:
            stock = InventoryStock(
                product=another_product,  # Producto diferente
                location=test_setup['location'],
                batch=test_setup['batch1'],  # Lote de otro producto
                quantity=50
            )
            stock.full_clean()
        
        assert "El lote no corresponde al producto seleccionado" in str(exc_info.value)

    def test_get_total_stock_method(self, test_setup):
        """Test del método get_total_stock que suma todos los lotes."""
        # Crear stock con diferentes lotes
        InventoryStock.objects.create(
            product=test_setup['batch_product'],
            location=test_setup['location'],
            batch=test_setup['batch1'],
            quantity=50
        )
        
        InventoryStock.objects.create(
            product=test_setup['batch_product'],
            location=test_setup['location'],
            batch=test_setup['batch2'],
            quantity=30
        )
        
        total_stock = InventoryStock.get_total_stock(
            test_setup['batch_product'], 
            test_setup['location']
        )
        
        assert total_stock == 80

    def test_get_available_batches_method(self, test_setup):
        """Test del método get_available_batches que ordena por FIFO."""
        # Crear stock con diferentes lotes y cantidades
        stock1 = InventoryStock.objects.create(
            product=test_setup['batch_product'],
            location=test_setup['location'],
            batch=test_setup['batch1'],  # Vence 2026-01-15
            quantity=50
        )
        
        stock2 = InventoryStock.objects.create(
            product=test_setup['batch_product'],
            location=test_setup['location'],
            batch=test_setup['batch2'],  # Vence 2025-06-15 (antes)
            quantity=30
        )
        
        available_batches = InventoryStock.get_available_batches(
            test_setup['batch_product'], 
            test_setup['location']
        )
        
        # Debe estar ordenado por fecha de vencimiento (FIFO)
        batch_list = list(available_batches)
        assert len(batch_list) == 2
        assert batch_list[0] == stock2  # El que vence primero
        assert batch_list[1] == stock1  # El que vence después


@pytest.mark.django_db
class TestInventoryMovementWithBatches:
    """Tests para InventoryMovement con sistema de lotes."""

    def test_create_movement_with_batch(self, test_setup):
        """Test crear movimiento con lote."""
        movement = InventoryMovement.objects.create(
            product=test_setup['batch_product'],
            location=test_setup['location'],
            batch=test_setup['batch1'],
            movement_type='in',
            quantity=50,
            notes='Entrada con lote'
        )
        
        assert movement.batch == test_setup['batch1']
        assert movement.quantity == 50
        
        # Verificar que se creó el stock
        stock = InventoryStock.objects.get(
            product=test_setup['batch_product'],
            location=test_setup['location'],
            batch=test_setup['batch1']
        )
        assert stock.quantity == 50

    def test_movement_requires_batch_validation(self, test_setup):
        """Test que falla al crear movimiento sin lote para producto que requiere control."""
        with pytest.raises(ValidationError) as exc_info:
            movement = InventoryMovement(
                product=test_setup['batch_product'],  # Requiere lote
                location=test_setup['location'],
                batch=None,  # Sin lote
                movement_type='in',
                quantity=50
            )
            movement.full_clean()
        
        assert "Este producto requiere especificar un lote" in str(exc_info.value)

    def test_movement_no_batch_for_no_batch_product(self, test_setup):
        """Test crear movimiento sin lote para producto que no requiere control."""
        movement = InventoryMovement.objects.create(
            product=test_setup['no_batch_product'],
            location=test_setup['location'],
            movement_type='in',
            quantity=25,
            notes='Entrada sin lote'
        )
        
        assert movement.batch is None
        assert movement.quantity == 25
        
        # Verificar que se creó el stock sin lote
        stock = InventoryStock.objects.get(
            product=test_setup['no_batch_product'],
            location=test_setup['location'],
            batch=None
        )
        assert stock.quantity == 25

    def test_insufficient_stock_by_batch(self, test_setup):
        """Test que falla al intentar sacar más stock del disponible en un lote específico."""
        # Crear stock inicial
        InventoryStock.objects.create(
            product=test_setup['batch_product'],
            location=test_setup['location'],
            batch=test_setup['batch1'],
            quantity=20
        )
        
        with pytest.raises(ValidationError) as exc_info:
            movement = InventoryMovement(
                product=test_setup['batch_product'],
                location=test_setup['location'],
                batch=test_setup['batch1'],
                movement_type='out',
                quantity=30  # Más de lo disponible (20)
            )
            movement.full_clean()
        
        assert "Stock insuficiente" in str(exc_info.value)
        assert "Disponible: 20" in str(exc_info.value)


@pytest.mark.django_db
class TestCompositeProductMovements:
    """Tests para movimientos de productos compuestos."""

    def test_composite_movement_creates_component_movements(self, test_setup):
        """Test que al mover producto compuesto se crean movimientos de componentes."""
        # Entrada de producto compuesto
        composite_movement = InventoryMovement.objects.create(
            product=test_setup['composite_product'],
            location=test_setup['location'],
            movement_type='in',
            quantity=5,  # 5 cajas
            notes='Entrada de cajas'
        )
        
        # Verificar que se creó movimiento del componente automáticamente
        component_movements = InventoryMovement.objects.filter(
            product=test_setup['component_product'],
            movement_type='in',
            related_composite_movement=composite_movement
        )
        
        assert component_movements.count() == 1
        component_movement = component_movements.first()
        assert component_movement.quantity == 50  # 5 cajas * 10 blisters cada una
        assert "Movimiento automático por ingreso de" in component_movement.notes

    def test_composite_breakdown_method(self, test_setup):
        """Test del método create_composite_breakdown."""
        # Crear stock inicial del producto compuesto
        InventoryStock.objects.create(
            product=test_setup['composite_product'],
            location=test_setup['location'],
            quantity=3
        )
        
        # Desarmar producto compuesto
        breakdown_movement = InventoryMovement.create_composite_breakdown(
            composite_product=test_setup['composite_product'],
            location=test_setup['location'],
            quantity=2,  # Desarmar 2 cajas
            notes='Desarmado para venta individual'
        )
        
        # Verificar que se creó el movimiento de salida del compuesto
        assert breakdown_movement.product == test_setup['composite_product']
        assert breakdown_movement.movement_type == 'out'
        assert breakdown_movement.quantity == 2
        
        # Verificar que se creó movimiento de entrada del componente
        component_movements = InventoryMovement.objects.filter(
            product=test_setup['component_product'],
            movement_type='in',  # Para breakdown, los componentes deberían tener movimento 'in'
            related_composite_movement=breakdown_movement
        )
        
        assert component_movements.count() == 1
        component_movement = component_movements.first()
        assert component_movement.quantity == 20  # 2 cajas * 10 blisters
        
        # Verificar stock final
        composite_stock = InventoryStock.objects.get(
            product=test_setup['composite_product'],
            location=test_setup['location']
        )
        assert composite_stock.quantity == 1  # 3 - 2 = 1
        
        component_stock = InventoryStock.objects.get(
            product=test_setup['component_product'],
            location=test_setup['location']
        )
        assert component_stock.quantity == 20  # 0 + 20 = 20

    def test_composite_sale_movement(self, test_setup):
        """Test movimiento de venta de producto compuesto."""
        # Crear stock inicial
        InventoryStock.objects.create(
            product=test_setup['composite_product'],
            location=test_setup['location'],
            quantity=5
        )
        
        # Venta de producto compuesto (movimiento de salida)
        sale_movement = InventoryMovement.objects.create(
            product=test_setup['composite_product'],
            location=test_setup['location'],
            movement_type='out',
            quantity=2,
            notes='Venta de cajas'
        )
        
        # Verificar que se creó movimiento de conversión del componente
        component_movements = InventoryMovement.objects.filter(
            product=test_setup['component_product'],
            movement_type='composite_conversion',
            related_composite_movement=sale_movement
        )
        
        assert component_movements.count() == 1
        component_movement = component_movements.first()
        assert component_movement.quantity == 20  # 2 cajas * 10 blisters
        assert "Movimiento automático por venta de" in component_movement.notes 
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from sales.models import Sale, SaleItem, Customer
from sales.serializers import SaleSerializer, SaleItemSerializer
from catalogs.models import Product, ProductBatch, Category
from inventory.models import Location, InventoryStock, InventoryMovement


@pytest.fixture
def test_setup():
    """Configuración de datos de prueba para ventas con lotes."""
    
    # Crear categoría
    category = Category.objects.create(
        name="Medicamentos",
        description="Productos farmacéuticos"
    )
    
    # Crear productos
    batch_product = Product.objects.create(
        name="Amoxicilina 500mg",
        sku="AMX-500",
        description="Antibiótico",
        category=category,
        requires_batch_control=True
    )
    
    no_batch_product = Product.objects.create(
        name="Algodón",
        sku="ALG-001",
        description="Material quirúrgico",
        category=category,
        requires_batch_control=False
    )
    
    # Crear ubicación
    location = Location.objects.create(
        name="Sede Principal",
        type="sede",
        address="Calle 123"
    )
    
    # Crear lotes
    batch1 = ProductBatch.objects.create(
        product=batch_product,
        batch_number="LOT-2024-001",
        expiry_date="2025-12-31"
    )
    
    batch2 = ProductBatch.objects.create(
        product=batch_product,
        batch_number="LOT-2024-002",
        expiry_date="2025-06-30"
    )
    
    # Crear stock
    InventoryStock.objects.create(
        product=batch_product,
        location=location,
        batch=batch1,
        quantity=50
    )
    
    InventoryStock.objects.create(
        product=batch_product,
        location=location,
        batch=batch2,
        quantity=30
    )
    
    InventoryStock.objects.create(
        product=no_batch_product,
        location=location,
        batch=None,
        quantity=100
    )
    
    # Crear cliente
    customer = Customer.objects.create(
        name="Juan Pérez",
        email="juan@example.com"
    )
    
    return {
        'batch_product': batch_product,
        'no_batch_product': no_batch_product,
        'location': location,
        'batch1': batch1,
        'batch2': batch2,
        'customer': customer
    }


@pytest.mark.django_db
class TestSaleItemWithBatches:
    """Tests para SaleItem con manejo de lotes."""

    def test_create_sale_item_with_batch(self, test_setup):
        """Test crear item de venta con lote."""
        sale = Sale.objects.create(
            customer=test_setup['customer'],
            location=test_setup['location']
        )
        
        item = SaleItem.objects.create(
            sale=sale,
            product=test_setup['batch_product'],
            batch=test_setup['batch1'],
            quantity=5,
            unit_price=Decimal('10000.00')
        )
        
        assert item.batch == test_setup['batch1']
        assert item.product == test_setup['batch_product']
        assert "Lote: LOT-2024-001" in str(item)

    def test_create_sale_item_without_batch_for_no_batch_product(self, test_setup):
        """Test crear item de venta sin lote para producto que no requiere control."""
        sale = Sale.objects.create(
            customer=test_setup['customer'],
            location=test_setup['location']
        )
        
        item = SaleItem.objects.create(
            sale=sale,
            product=test_setup['no_batch_product'],
            batch=None,
            quantity=10,
            unit_price=Decimal('5000.00')
        )
        
        assert item.batch is None
        assert item.product == test_setup['no_batch_product']

    def test_validation_batch_required_for_batch_product(self, test_setup):
        """Test que falla al crear item sin lote para producto que requiere control."""
        sale = Sale.objects.create(
            customer=test_setup['customer'],
            location=test_setup['location']
        )
        
        with pytest.raises(ValidationError) as exc_info:
            item = SaleItem(
                sale=sale,
                product=test_setup['batch_product'],
                batch=None,
                quantity=5,
                unit_price=Decimal('10000.00')
            )
            item.full_clean()
        
        assert "Este producto requiere especificar un lote" in str(exc_info.value)

    def test_validation_batch_not_allowed_for_no_batch_product(self, test_setup):
        """Test que falla al especificar lote para producto que no requiere control."""
        sale = Sale.objects.create(
            customer=test_setup['customer'],
            location=test_setup['location']
        )
        
        with pytest.raises(ValidationError) as exc_info:
            item = SaleItem(
                sale=sale,
                product=test_setup['no_batch_product'],
                batch=test_setup['batch1'],
                quantity=5,
                unit_price=Decimal('10000.00')
            )
            item.full_clean()
        
        assert "Este producto no requiere control de lotes" in str(exc_info.value)

    def test_validation_batch_product_mismatch(self, test_setup):
        """Test que falla al usar lote de otro producto."""
        sale = Sale.objects.create(
            customer=test_setup['customer'],
            location=test_setup['location']
        )
        
        # Crear otro producto con su lote
        other_product = Product.objects.create(
            name="Ibuprofeno",
            sku="IBU-001",
            requires_batch_control=True,
            category=test_setup['batch_product'].category
        )
        
        with pytest.raises(ValidationError) as exc_info:
            item = SaleItem(
                sale=sale,
                product=other_product,
                batch=test_setup['batch1'],  # Lote de otro producto
                quantity=5,
                unit_price=Decimal('10000.00')
            )
            item.full_clean()
        
        assert "El lote no corresponde al producto seleccionado" in str(exc_info.value)


@pytest.mark.django_db
class TestSaleSerializerWithBatches:
    """Tests para SaleSerializer con manejo de lotes."""

    def test_create_sale_with_batches(self, test_setup):
        """Test crear venta con items que tienen lotes."""
        sale_data = {
            'customer': test_setup['customer'].id,
            'location': test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': test_setup['batch_product'].id,
                    'batch': test_setup['batch1'].id,
                    'quantity': 10,
                    'unit_price': '15000.00'
                },
                {
                    'product': test_setup['no_batch_product'].id,
                    'quantity': 5,
                    'unit_price': '8000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        assert sale.items.count() == 2
        
        # Verificar item con lote
        batch_item = sale.items.filter(product=test_setup['batch_product']).first()
        assert batch_item.batch == test_setup['batch1']
        assert batch_item.quantity == 10
        
        # Verificar item sin lote
        no_batch_item = sale.items.filter(product=test_setup['no_batch_product']).first()
        assert no_batch_item.batch is None
        assert no_batch_item.quantity == 5
        
        # Verificar que se crearon movimientos de inventario
        movements = InventoryMovement.objects.filter(
            notes__contains=f'Venta #{sale.id}'
        )
        assert movements.count() == 2
        
        # Verificar movimiento con lote
        batch_movement = movements.filter(batch=test_setup['batch1']).first()
        assert batch_movement is not None
        assert batch_movement.quantity == 10
        
        # Verificar movimiento sin lote
        no_batch_movement = movements.filter(batch__isnull=True).first()
        assert no_batch_movement is not None
        assert no_batch_movement.quantity == 5

    def test_insufficient_batch_stock_validation(self, test_setup):
        """Test validación de stock insuficiente en lote específico."""
        sale_data = {
            'customer': test_setup['customer'].id,
            'location': test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': test_setup['batch_product'].id,
                    'batch': test_setup['batch1'].id,
                    'quantity': 60,  # Stock disponible es 50
                    'unit_price': '15000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        
        with pytest.raises(DRFValidationError) as exc_info:
            serializer.save()
        
        error_message = str(exc_info.value)
        assert "Stock insuficiente del lote LOT-2024-001" in error_message
        assert "Disponible: 50" in error_message
        assert "Solicitado: 60" in error_message

    def test_missing_batch_for_batch_product(self, test_setup):
        """Test validación de lote faltante para producto que requiere control."""
        sale_data = {
            'customer': test_setup['customer'].id,
            'location': test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': test_setup['batch_product'].id,
                    # 'batch': falta este campo
                    'quantity': 10,
                    'unit_price': '15000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert not serializer.is_valid()
        assert 'batch' in str(serializer.errors)

    def test_batch_stock_reduction(self, test_setup):
        """Test que el stock del lote se reduce correctamente."""
        initial_stock = InventoryStock.objects.get(
            product=test_setup['batch_product'],
            location=test_setup['location'],
            batch=test_setup['batch1']
        ).quantity
        
        sale_data = {
            'customer': test_setup['customer'].id,
            'location': test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': test_setup['batch_product'].id,
                    'batch': test_setup['batch1'].id,
                    'quantity': 15,
                    'unit_price': '15000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que el stock se redujo
        updated_stock = InventoryStock.objects.get(
            product=test_setup['batch_product'],
            location=test_setup['location'],
            batch=test_setup['batch1']
        )
        assert updated_stock.quantity == initial_stock - 15

    def test_nonexistent_batch_stock(self, test_setup):
        """Test validación cuando no existe stock del lote en la ubicación."""
        # Crear un lote sin stock
        batch3 = ProductBatch.objects.create(
            product=test_setup['batch_product'],
            batch_number="LOT-2024-003",
            expiry_date="2025-03-31"
        )
        
        sale_data = {
            'customer': test_setup['customer'].id,
            'location': test_setup['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': test_setup['batch_product'].id,
                    'batch': batch3.id,
                    'quantity': 5,
                    'unit_price': '15000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        
        with pytest.raises(DRFValidationError) as exc_info:
            serializer.save()
        
        error_message = str(exc_info.value)
        assert "No hay stock del lote LOT-2024-003" in error_message 
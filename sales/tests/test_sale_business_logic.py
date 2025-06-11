import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from decimal import Decimal

from sales.models import Customer, Sale, SaleItem
from inventory.models import Location, InventoryStock, InventoryMovement
from catalogs.models import Category, Product

User = get_user_model()


@pytest.fixture
def test_user():
    """Fixture para crear un usuario de prueba."""
    return User.objects.create_user(
        username='testuser_sales',
        email='testuser_sales@example.com',
        password='TestPass123!'
    )


@pytest.fixture
def test_data():
    """Fixture para crear datos de prueba."""
    # Crear categoría y producto
    category = Category.objects.create(
        name='Test Category Sales', 
        description='For sales tests'
    )
    product = Product.objects.create(
        sku='SALE-TEST-001',
        name='Test Product Sales',
        description='Product for sales testing',
        unit='unidad',
        category=category
    )
    
    # Crear ubicación y stock
    location = Location.objects.create(
        name='Test Location Sales',
        type='bodega'
    )
    
    inventory_stock = InventoryStock.objects.create(
        product=product,
        location=location,
        quantity=100
    )
    
    # Crear cliente
    customer = Customer.objects.create(
        name='Cliente Test',
        phone='123456789',
        email='cliente@test.com',
        notes='Cliente para pruebas'
    )
    
    return {
        'category': category,
        'product': product,
        'location': location,
        'inventory_stock': inventory_stock,
        'customer': customer
    }


@pytest.mark.django_db
class TestCustomerBusinessLogic:
    """Tests para la lógica de negocio de clientes."""

    def test_create_customer_basic(self):
        """Prueba crear un cliente básico."""
        customer = Customer.objects.create(
            name='Juan Pérez',
            phone='987654321',
            email='juan@example.com'
        )
        
        assert customer.name == 'Juan Pérez'
        assert customer.phone == '987654321'
        assert customer.email == 'juan@example.com'
        assert customer.notes == None

    def test_customer_string_representation(self):
        """Prueba representación string de cliente."""
        customer = Customer.objects.create(name='María López')
        assert str(customer) == 'María López'

    def test_customer_optional_fields(self):
        """Prueba campos opcionales de cliente."""
        customer = Customer.objects.create(name='Pedro Gómez')
        assert customer.phone is None
        assert customer.email is None
        assert customer.notes is None


@pytest.mark.django_db
class TestSaleBusinessLogic:
    """Tests para la lógica de negocio de ventas."""

    def test_create_sale_basic(self, test_data):
        """Prueba crear una venta básica."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location'],
            sale_type='normal'
        )
        
        assert sale.customer == test_data['customer']
        assert sale.location == test_data['location']
        assert sale.sale_type == 'normal'
        assert sale.should_invoice is True
        assert sale.total_gross == Decimal('0')
        assert sale.total_net == Decimal('0')

    def test_sale_without_customer(self, test_data):
        """Prueba crear una venta anónima."""
        sale = Sale.objects.create(
            location=test_data['location'],
            sale_type='normal'
        )
        assert sale.customer is None
        assert sale.location == test_data['location']

    def test_sale_type_validation(self, test_data):
        """Prueba validación de tipo de venta."""
        with pytest.raises(ValidationError):
            sale = Sale(
                location=test_data['location'],
                sale_type='invalid'
            )
            sale.full_clean()

    def test_sale_string_representation(self, test_data):
        """Prueba representación string de venta."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        expected = f"Venta {sale.id} - {test_data['customer'].name} - {test_data['location'].name} - {sale.sale_date}"
        assert str(sale) == expected

    def test_anonymous_sale_string_representation(self, test_data):
        """Prueba representación string de venta anónima."""
        sale = Sale.objects.create(location=test_data['location'])
        expected = f"Venta {sale.id} - Anónimo - {test_data['location'].name} - {sale.sale_date}"
        assert str(sale) == expected


@pytest.mark.django_db
class TestSaleItemBusinessLogic:
    """Tests para la lógica de negocio de items de venta."""

    def test_create_sale_item_basic(self, test_data):
        """Prueba crear un item de venta básico."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=test_data['product'],
            quantity=2,
            unit_price=Decimal('50000.00')
        )
        
        assert item.sale == sale
        assert item.product == test_data['product']
        assert item.quantity == 2
        assert item.unit_price == Decimal('50000.00')

    def test_sale_total_calculation(self, test_data):
        """Prueba cálculo de totales de venta."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        
        # Crear dos items
        SaleItem.objects.create(
            sale=sale,
            product=test_data['product'],
            quantity=2,
            unit_price=Decimal('50000.00')
        )
        
        # El total debe ser 100000
        sale.refresh_from_db()
        assert sale.total_gross == Decimal('100000.00')
        assert sale.total_net == Decimal('100000.00')

    def test_negative_quantity_validation(self, test_data):
        """Prueba validación de cantidad negativa."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        
        with pytest.raises(ValidationError):
            item = SaleItem(
                sale=sale,
                product=test_data['product'],
                quantity=-1,
                unit_price=Decimal('50000.00')
            )
            item.full_clean()

    def test_zero_quantity_validation(self, test_data):
        """Prueba validación de cantidad cero."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        
        with pytest.raises(ValidationError):
            item = SaleItem(
                sale=sale,
                product=test_data['product'],
                quantity=0,
                unit_price=Decimal('50000.00')
            )
            item.full_clean()

    def test_negative_price_validation(self, test_data):
        """Prueba validación de precio negativo."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        
        with pytest.raises(ValidationError):
            item = SaleItem(
                sale=sale,
                product=test_data['product'],
                quantity=1,
                unit_price=Decimal('-1000.00')
            )
            item.full_clean()

    def test_stock_reduction(self, test_data):
        """Prueba reducción de stock al crear item."""
        from sales.serializers import SaleSerializer
        
        initial_stock = test_data['inventory_stock'].quantity
        
        # Usar el serializador para crear la venta con items
        sale_data = {
            'customer': test_data['customer'].id,
            'location': test_data['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': test_data['product'].id,
                    'quantity': 5,
                    'unit_price': '50000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        assert serializer.is_valid(), serializer.errors
        sale = serializer.save()
        
        # Verificar que se creó el movimiento de inventario
        movement = InventoryMovement.objects.filter(
            product=test_data['product'],
            movement_type='out',
            quantity=5
        ).first()
        assert movement is not None
        assert f'Venta #{sale.id}' in movement.notes
        
        # Verificar que se actualizó el stock
        test_data['inventory_stock'].refresh_from_db()
        assert test_data['inventory_stock'].quantity == initial_stock - 5

    def test_insufficient_stock_validation(self, test_data):
        """Prueba validación de stock insuficiente."""
        from sales.serializers import SaleSerializer
        
        # Usar el serializador completo para probar la validación de stock por sede
        sale_data = {
            'customer': test_data['customer'].id,
            'location': test_data['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': test_data['product'].id,
                    'quantity': 101,  # Stock es 100
                    'unit_price': '50000.00'
                }
            ]
        }
        
        serializer = SaleSerializer(data=sale_data)
        # Verificar que el serializador en sí es válido pero falla en la creación
        if serializer.is_valid():
            # Si es válido, debería fallar en save() debido a stock insuficiente
            with pytest.raises(Exception):  # Puede ser ValidationError o ValueError
                serializer.save()
        else:
            # Si no es válido, verificar que el error sea sobre stock
            assert 'items' in serializer.errors or 'non_field_errors' in serializer.errors


@pytest.mark.django_db
class TestSaleDataIntegrity:
    """Tests para la integridad de datos en ventas."""

    def test_cascade_delete_sale_affects_items(self, test_data):
        """Prueba eliminación en cascada de items al eliminar venta."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=test_data['product'],
            quantity=1,
            unit_price=Decimal('50000.00')
        )
        
        sale_id = sale.id
        sale.delete()
        
        with pytest.raises(SaleItem.DoesNotExist):
            SaleItem.objects.get(id=item.id)

    def test_protect_product_from_deletion(self, test_data):
        """Prueba que no se puede eliminar producto con ventas asociadas."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=test_data['product'],
            quantity=1,
            unit_price=Decimal('50000.00')
        )
        
        with pytest.raises(IntegrityError):
            test_data['product'].delete()

    def test_allow_customer_deletion(self, test_data):
        """Prueba que se permite eliminar cliente con ventas (SET_NULL)."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        customer_id = test_data['customer'].id
        test_data['customer'].delete()
        
        sale.refresh_from_db()
        assert sale.customer is None 
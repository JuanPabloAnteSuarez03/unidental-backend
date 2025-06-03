import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from decimal import Decimal

from purchases.models import PurchaseOrder, PurchaseOrderItem
from suppliers.models import Supplier, PurchaseOption
from inventory.models import Location
from catalogs.models import Category, Product

User = get_user_model()


@pytest.fixture
def test_user():
    """Fixture para crear un usuario de prueba."""
    return User.objects.create_user(
        username='testuser_purchases',
        email='testuser_purchases@example.com',
        password='TestPass123!'
    )


@pytest.fixture
def test_data():
    """Fixture para crear datos de prueba."""
    # Crear categoría y producto
    category = Category.objects.create(
        name='Test Category Purchases', 
        description='For purchases tests'
    )
    product = Product.objects.create(
        sku='PUR-TEST-001',
        name='Test Product Purchases',
        description='Product for purchases testing',
        unit='caja',
        category=category
    )
    
    # Crear proveedor
    supplier = Supplier.objects.create(
        name='Proveedor Test Purchases',
        contact_name='Juan Pérez',
        phone='123456789',
        email='proveedor@test.com'
    )
    
    # Crear opción de compra
    purchase_option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Marca Test',
        purchase_price=Decimal('25000.00')
    )
    
    # Crear ubicaciones
    sede = Location.objects.create(
        name='Sede Test Purchases', 
        type='sede', 
        address='Test Address'
    )
    bodega = Location.objects.create(
        name='Bodega Test Purchases', 
        type='bodega', 
        address='Test Warehouse'
    )
    
    return {
        'category': category,
        'product': product,
        'supplier': supplier,
        'purchase_option': purchase_option,
        'sede': sede,
        'bodega': bodega
    }


@pytest.mark.django_db
class TestPurchaseOrderBusinessLogic:
    """Tests para la lógica de negocio de órdenes de compra."""

    def test_create_purchase_order_basic(self, test_data, test_user):
        """Prueba crear una orden de compra básica."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user,
            notes='Orden de prueba'
        )
        
        assert order.supplier == test_data['supplier']
        assert order.destination == test_data['sede']
        assert order.status == 'pending'
        assert order.created_by == test_user
        assert order.order_date == date.today()
        assert order.can_be_modified() is True

    def test_purchase_order_default_values(self, test_data, test_user):
        """Prueba valores por defecto de orden de compra."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        assert order.status == 'pending'
        assert order.order_date == date.today()
        assert order.notes == ''

    def test_purchase_order_string_representation(self, test_data, test_user):
        """Prueba representación string de orden de compra."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        expected = f"Orden #{order.id} - {test_data['supplier'].name} (Pendiente)"
        assert str(order) == expected

    def test_future_order_date_validation(self, test_data, test_user):
        """Prueba validación de fecha futura."""
        future_date = date.today() + timedelta(days=1)
        
        order = PurchaseOrder(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            order_date=future_date,
            created_by=test_user
        )
        
        with pytest.raises(ValidationError) as exc_info:
            order.full_clean()
        
        assert 'order_date' in exc_info.value.message_dict

    def test_cancel_pending_order(self, test_data, test_user):
        """Prueba cancelar orden pendiente."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        result = order.cancel_order()
        assert result is True
        assert order.status == 'canceled'
        assert order.can_be_modified() is False

    def test_cannot_cancel_received_order(self, test_data, test_user):
        """Prueba que no se puede cancelar orden recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='received',
            created_by=test_user
        )
        
        result = order.cancel_order()
        assert result is False
        assert order.status == 'received'

    def test_mark_as_received(self, test_data, test_user):
        """Prueba marcar orden como recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        result = order.mark_as_received()
        assert result is True
        assert order.status == 'received'
        assert order.can_be_modified() is False

    def test_cannot_mark_canceled_as_received(self, test_data, test_user):
        """Prueba que no se puede marcar orden cancelada como recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='canceled',
            created_by=test_user
        )
        
        result = order.mark_as_received()
        assert result is False
        assert order.status == 'canceled'

    def test_order_modification_permissions(self, test_data, test_user):
        """Prueba permisos de modificación según estado."""
        # Orden pendiente puede modificarse
        pending_order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='pending',
            created_by=test_user
        )
        assert pending_order.can_be_modified() is True
        
        # Orden recibida no puede modificarse
        received_order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='received',
            created_by=test_user
        )
        assert received_order.can_be_modified() is False
        
        # Orden cancelada no puede modificarse
        canceled_order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='canceled',
            created_by=test_user
        )
        assert canceled_order.can_be_modified() is False


@pytest.mark.django_db
class TestPurchaseOrderItemBusinessLogic:
    """Tests para la lógica de negocio de items de orden de compra."""

    def test_create_purchase_order_item_basic(self, test_data, test_user):
        """Prueba crear un item de orden de compra básico."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        item = PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=10,
            unit_price=Decimal('25000.00')
        )
        
        assert item.order == order
        assert item.purchase_option == test_data['purchase_option']
        assert item.quantity_requested == 10
        assert item.unit_price == Decimal('25000.00')

    def test_line_total_calculation(self, test_data, test_user):
        """Prueba cálculo del total de línea."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        item = PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('25000.00')
        )
        
        expected_total = Decimal('125000.00')
        assert item.line_total == expected_total

    def test_purchase_order_item_string_representation(self, test_data, test_user):
        """Prueba representación string de item."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        item = PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('25000.00')
        )
        
        expected = f"{test_data['product'].name} - {test_data['purchase_option'].brand} (x5)"
        assert str(item) == expected

    def test_supplier_mismatch_validation(self, test_data, test_user):
        """Prueba validación de proveedor diferente."""
        # Crear otro proveedor
        another_supplier = Supplier.objects.create(
            name='Otro Proveedor',
            contact_name='María García',
            phone='987654321',
            email='otro@test.com'
        )
        
        # Crear opción de compra con otro proveedor
        another_option = PurchaseOption.objects.create(
            product=test_data['product'],
            supplier=another_supplier,
            brand='Otra Marca',
            purchase_price=Decimal('30000.00')
        )
        
        # Crear orden con primer proveedor
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        # Intentar crear item con proveedor diferente
        item = PurchaseOrderItem(
            order=order,
            purchase_option=another_option,
            quantity_requested=5,
            unit_price=Decimal('30000.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            item.full_clean()
        
        assert 'purchase_option' in exc_info.value.message_dict

    def test_zero_quantity_validation(self, test_data, test_user):
        """Prueba validación de cantidad cero."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        item = PurchaseOrderItem(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=0,
            unit_price=Decimal('25000.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            item.full_clean()
        
        assert 'quantity_requested' in exc_info.value.message_dict

    def test_negative_quantity_validation(self, test_data, test_user):
        """Prueba validación de cantidad negativa."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        item = PurchaseOrderItem(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=-5,
            unit_price=Decimal('25000.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            item.save()  # PositiveIntegerField validation happens at save

    def test_zero_price_validation(self, test_data, test_user):
        """Prueba validación de precio cero."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        item = PurchaseOrderItem(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('0.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            item.full_clean()
        
        assert 'unit_price' in exc_info.value.message_dict

    def test_negative_price_validation(self, test_data, test_user):
        """Prueba validación de precio negativo."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        item = PurchaseOrderItem(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('-1000.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            item.full_clean()
        
        assert 'unit_price' in exc_info.value.message_dict

    def test_cannot_add_item_to_non_modifiable_order(self, test_data, test_user):
        """Prueba que no se pueden agregar items a órdenes no modificables."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='received',
            created_by=test_user
        )
        
        item = PurchaseOrderItem(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('25000.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            item.full_clean()
        
        assert 'order' in exc_info.value.message_dict


@pytest.mark.django_db
class TestPurchaseOrderCalculations:
    """Tests para cálculos y propiedades de orden de compra."""

    def test_total_amount_calculation(self, test_data, test_user):
        """Prueba cálculo del monto total de la orden."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        # Crear otra opción de compra para el segundo item
        product2 = Product.objects.create(
            sku='PUR-TEST-002',
            name='Test Product 2',
            description='Second product for testing',
            unit='unidad',
            category=test_data['category']
        )
        
        purchase_option2 = PurchaseOption.objects.create(
            product=product2,
            supplier=test_data['supplier'],
            brand='Marca Test 2',
            purchase_price=Decimal('30000.00')
        )
        
        # Crear items
        PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('25000.00')
        )
        PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=purchase_option2,
            quantity_requested=3,
            unit_price=Decimal('30000.00')
        )
        
        expected_total = Decimal('125000.00') + Decimal('90000.00')
        assert order.total_amount == expected_total

    def test_total_items_calculation(self, test_data, test_user):
        """Prueba cálculo del total de items en la orden."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        # Crear otra opción de compra para el segundo item
        product2 = Product.objects.create(
            sku='PUR-TEST-003',
            name='Test Product 3',
            description='Third product for testing',
            unit='unidad',
            category=test_data['category']
        )
        
        purchase_option2 = PurchaseOption.objects.create(
            product=product2,
            supplier=test_data['supplier'],
            brand='Marca Test 3',
            purchase_price=Decimal('30000.00')
        )
        
        # Crear items
        PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('25000.00')
        )
        PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=purchase_option2,
            quantity_requested=3,
            unit_price=Decimal('30000.00')
        )
        
        assert order.total_items == 8

    def test_empty_order_calculations(self, test_data, test_user):
        """Prueba cálculos en orden vacía."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        assert order.total_amount == 0
        assert order.total_items == 0


@pytest.mark.django_db
class TestPurchaseDataIntegrity:
    """Tests para integridad de datos en purchases."""

    def test_unique_item_per_order_purchase_option(self, test_data, test_user):
        """Prueba constraint único de item por orden y opción de compra."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        # Crear primer item
        PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('25000.00')
        )
        
        # Intentar crear segundo item con misma orden y opción
        # La validación de unique_together se ejecuta en full_clean() que se llama en save()
        with pytest.raises(ValidationError):
            PurchaseOrderItem.objects.create(
                order=order,
                purchase_option=test_data['purchase_option'],
                quantity_requested=3,
                unit_price=Decimal('30000.00')
            )

    def test_cascade_delete_order_affects_items(self, test_data, test_user):
        """Prueba que eliminar orden elimina sus items."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        # Crear items
        item1 = PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('25000.00')
        )
        
        item_id = item1.id
        
        # Eliminar orden
        order.delete()
        
        # Verificar que items fueron eliminados
        assert not PurchaseOrderItem.objects.filter(id=item_id).exists()

    def test_cascade_delete_supplier_affects_orders(self, test_data, test_user):
        """Prueba que eliminar proveedor elimina sus órdenes."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        order_id = order.id
        
        # Eliminar proveedor
        test_data['supplier'].delete()
        
        # Verificar que orden fue eliminada
        assert not PurchaseOrder.objects.filter(id=order_id).exists()

    def test_cascade_delete_location_affects_orders(self, test_data, test_user):
        """Prueba que eliminar ubicación elimina sus órdenes."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        order_id = order.id
        
        # Eliminar ubicación
        test_data['sede'].delete()
        
        # Verificar que orden fue eliminada
        assert not PurchaseOrder.objects.filter(id=order_id).exists()

    def test_soft_delete_user_preserves_orders(self, test_data, test_user):
        """Prueba que eliminar usuario preserva órdenes (SET_NULL)."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            created_by=test_user
        )
        
        order_id = order.id
        
        # Eliminar usuario
        test_user.delete()
        
        # Verificar que orden existe pero created_by es None
        order.refresh_from_db()
        assert order.created_by is None 
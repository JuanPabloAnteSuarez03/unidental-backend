import pytest
from decimal import Decimal
from django.utils import timezone

from deliveries.models import Delivery
from deliveries.serializers import (
    DeliveryListSerializer, DeliveryDetailSerializer, DeliveryCreateSerializer,
    DeliveryUpdateSerializer, DeliveryStatusUpdateSerializer
)
from sales.models import Sale, Customer, SaleItem
from inventory.models import Location, InventoryStock
from catalogs.models import Category, Product


@pytest.fixture
def category():
    """Fixture que crea una categoría de muestra."""
    return Category.objects.create(
        name='Productos Dentales',
        description='Productos para clínicas dentales'
    )


@pytest.fixture
def product(category):
    """Fixture que crea un producto de muestra."""
    return Product.objects.create(
        sku='DENTAL-001',
        name='Jeringa Dental',
        description='Jeringa para procedimientos dentales',
        unit='unidad',
        category=category
    )


@pytest.fixture
def customer():
    """Fixture que crea un cliente de muestra."""
    return Customer.objects.create(
        name='Dr. Juan Pérez',
        phone='+57-300-123-4567',
        email='dr.perez@clinic.com',
        notes='Cliente VIP'
    )


@pytest.fixture
def origin_location():
    """Fixture que crea ubicación de origen."""
    return Location.objects.create(
        name='Bodega Principal',
        type='bodega'
    )


@pytest.fixture
def dest_location():
    """Fixture que crea ubicación de destino."""
    return Location.objects.create(
        name='Clínica Norte',
        type='bodega'
    )


@pytest.fixture
def inventory_stock(product, origin_location):
    """Fixture que crea stock de inventario."""
    return InventoryStock.objects.create(
        product=product,
        location=origin_location,
        quantity=50
    )


@pytest.fixture
def sale(customer, product, inventory_stock):
    """Fixture que crea una venta de muestra."""
    sale = Sale.objects.create(
        customer=customer,
        sale_type='normal',
        should_invoice=True
    )
    
    sale_item = SaleItem.objects.create(
        sale=sale,
        product=product,
        quantity=2,
        unit_price=Decimal('50000.00')
    )
    
    return sale


@pytest.fixture
def delivery(sale, origin_location, dest_location):
    """Fixture que crea una entrega de muestra."""
    return Delivery.objects.create(
        sale=sale,
        origin_location=origin_location,
        dest_location=dest_location,
        status='pending'
    )


# Tests para DeliveryListSerializer

@pytest.mark.django_db
def test_delivery_list_serializer_fields(delivery):
    """Test para verificar los campos del serializer de lista."""
    serializer = DeliveryListSerializer(delivery)
    data = serializer.data
    
    # Verificar campos principales
    assert 'id' in data
    assert 'sale' in data
    assert 'customer_name' in data
    assert 'sale_total' in data
    assert 'origin_location' in data
    assert 'origin_location_name' in data
    assert 'dest_location' in data
    assert 'dest_location_name' in data
    assert 'status' in data
    assert 'status_display' in data
    assert 'delivery_time' in data
    assert 'created_at' in data
    assert 'updated_at' in data


@pytest.mark.django_db
def test_delivery_list_serializer_computed_fields(delivery):
    """Test para verificar campos computados en el serializer de lista."""
    serializer = DeliveryListSerializer(delivery)
    data = serializer.data
    
    assert data['customer_name'] == delivery.customer_name
    # Convert both to string for comparison since serializer may return string
    assert str(data['sale_total']) == str(delivery.sale_total)
    assert data['status_display'] == delivery.get_status_display()
    assert data['origin_location_name'] == delivery.origin_location.name
    assert data['dest_location_name'] == delivery.dest_location.name


# Tests para DeliveryDetailSerializer

@pytest.mark.django_db
def test_delivery_detail_serializer_fields(delivery):
    """Test para verificar los campos del serializer detallado."""
    serializer = DeliveryDetailSerializer(delivery)
    data = serializer.data
    
    # Verificar campos básicos
    assert 'id' in data
    assert 'sale' in data
    assert 'customer_name' in data
    assert 'sale_total' in data
    assert 'status' in data
    assert 'status_display' in data
    
    # Verificar campos de estado
    assert 'is_pending' in data
    assert 'is_in_transit' in data
    assert 'is_delivered' in data
    assert 'can_be_modified' in data
    
    # Verificar relaciones anidadas
    assert isinstance(data['sale'], dict)
    assert isinstance(data['origin_location'], dict)
    assert isinstance(data['dest_location'], dict)


@pytest.mark.django_db
def test_delivery_detail_serializer_status_fields(delivery):
    """Test para verificar campos de estado en el serializer detallado."""
    serializer = DeliveryDetailSerializer(delivery)
    data = serializer.data
    
    # Estado inicial: pending
    assert data['is_pending'] is True
    assert data['is_in_transit'] is False
    assert data['is_delivered'] is False
    assert data['can_be_modified'] is True


# Tests para DeliveryCreateSerializer

@pytest.mark.django_db
def test_delivery_create_serializer_valid_data(sale, origin_location, dest_location):
    """Test para crear entrega con datos válidos."""
    data = {
        'sale': sale.id,
        'origin_location': origin_location.id,
        'dest_location': dest_location.id,
        'status': 'pending'
    }
    
    serializer = DeliveryCreateSerializer(data=data)
    assert serializer.is_valid()
    
    delivery = serializer.save()
    assert delivery.sale == sale
    assert delivery.origin_location == origin_location
    assert delivery.dest_location == dest_location
    assert delivery.status == 'pending'


@pytest.mark.django_db
def test_delivery_create_serializer_duplicate_sale(delivery, dest_location):
    """Test para verificar que no se puede crear entrega para venta existente."""
    data = {
        'sale': delivery.sale.id,  # Venta ya tiene entrega
        'origin_location': delivery.origin_location.id,
        'dest_location': dest_location.id,
        'status': 'pending'
    }
    
    serializer = DeliveryCreateSerializer(data=data)
    assert not serializer.is_valid()
    assert 'sale' in serializer.errors


@pytest.mark.django_db
def test_delivery_create_serializer_same_locations(sale, origin_location):
    """Test para verificar que no se pueden usar las mismas ubicaciones."""
    data = {
        'sale': sale.id,
        'origin_location': origin_location.id,
        'dest_location': origin_location.id,  # Misma ubicación
        'status': 'pending'
    }
    
    serializer = DeliveryCreateSerializer(data=data)
    assert not serializer.is_valid()
    assert 'dest_location' in serializer.errors


# Tests para DeliveryUpdateSerializer

@pytest.mark.django_db
def test_delivery_update_serializer_valid_data(delivery, dest_location):
    """Test para actualizar entrega con datos válidos."""
    # Crear nueva ubicación de destino
    new_dest = Location.objects.create(name='Nueva Clínica', type='bodega')
    
    data = {
        'dest_location': new_dest.id
    }
    
    serializer = DeliveryUpdateSerializer(delivery, data=data, partial=True)
    assert serializer.is_valid()
    
    updated_delivery = serializer.save()
    assert updated_delivery.dest_location == new_dest


@pytest.mark.django_db
def test_delivery_update_serializer_delivered_status_change(delivery):
    """Test para verificar que no se puede cambiar estado de entrega entregada."""
    # Marcar como entregada
    delivery.mark_as_delivered()
    
    data = {
        'status': 'pending'
    }
    
    serializer = DeliveryUpdateSerializer(delivery, data=data, partial=True)
    assert not serializer.is_valid()
    assert 'status' in serializer.errors


@pytest.mark.django_db
def test_delivery_update_serializer_same_locations_validation(delivery):
    """Test para validar ubicaciones diferentes en actualización."""
    data = {
        'dest_location': delivery.origin_location.id  # Misma que origen
    }
    
    serializer = DeliveryUpdateSerializer(delivery, data=data, partial=True)
    assert not serializer.is_valid()
    assert 'dest_location' in serializer.errors


# Tests para DeliveryStatusUpdateSerializer

@pytest.mark.django_db
def test_delivery_status_update_serializer_valid_transition(delivery):
    """Test para transición válida de estado."""
    data = {'status': 'in_transit'}
    
    serializer = DeliveryStatusUpdateSerializer(delivery, data=data)
    assert serializer.is_valid()


@pytest.mark.django_db
def test_delivery_status_update_serializer_invalid_transition(delivery):
    """Test para transición inválida de estado."""
    # Marcar como entregada primero
    delivery.mark_as_delivered()
    
    data = {'status': 'pending'}
    
    serializer = DeliveryStatusUpdateSerializer(delivery, data=data)
    assert not serializer.is_valid()
    assert 'status' in serializer.errors


@pytest.mark.django_db
def test_delivery_status_update_serializer_skip_states(delivery):
    """Test para transición que salta estados."""
    # De pending directamente a delivered debería ser válido
    data = {'status': 'delivered'}
    
    serializer = DeliveryStatusUpdateSerializer(delivery, data=data)
    assert serializer.is_valid()


@pytest.mark.django_db
def test_delivery_status_update_serializer_same_status(delivery):
    """Test para mantener el mismo estado."""
    data = {'status': 'pending'}
    
    serializer = DeliveryStatusUpdateSerializer(delivery, data=data)
    # Debería ser inválido porque pending no está en las transiciones válidas desde pending
    assert not serializer.is_valid()


# Tests de integración con relaciones

@pytest.mark.django_db
def test_delivery_serializer_with_anonymous_sale(origin_location, dest_location, product, inventory_stock):
    """Test para serializer con venta anónima."""
    # Crear venta anónima
    sale = Sale.objects.create(
        customer=None,  # Sin cliente
        sale_type='normal',
        should_invoice=False
    )
    
    SaleItem.objects.create(
        sale=sale,
        product=product,
        quantity=1,
        unit_price=Decimal('25000.00')
    )
    
    delivery = Delivery.objects.create(
        sale=sale,
        origin_location=origin_location,
        dest_location=dest_location,
        status='pending'
    )
    
    serializer = DeliveryDetailSerializer(delivery)
    data = serializer.data
    
    assert data['customer_name'] == 'Cliente Anónimo'


@pytest.mark.django_db
def test_delivery_serializer_with_shipped_delivery(delivery):
    """Test para serializer con entrega enviada."""
    delivery.mark_as_shipped()
    
    serializer = DeliveryDetailSerializer(delivery)
    data = serializer.data
    
    assert data['is_pending'] is False
    assert data['is_in_transit'] is True
    assert data['is_delivered'] is False
    assert data['can_be_modified'] is False
    assert data['shipped_at'] is not None


@pytest.mark.django_db
def test_delivery_serializer_with_delivered_delivery(delivery):
    """Test para serializer con entrega entregada."""
    delivery.mark_as_delivered()
    
    serializer = DeliveryDetailSerializer(delivery)
    data = serializer.data
    
    assert data['is_pending'] is False
    assert data['is_in_transit'] is False
    assert data['is_delivered'] is True
    assert data['can_be_modified'] is False
    assert data['shipped_at'] is not None
    assert data['delivered_at'] is not None
    assert data['delivery_time'] == 0  # Mismo día 
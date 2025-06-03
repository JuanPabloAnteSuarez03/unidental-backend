import pytest
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from deliveries.models import Delivery
from deliveries.filters import DeliveryFilter
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
def another_customer():
    """Fixture que crea otro cliente."""
    return Customer.objects.create(
        name='Dra. María García',
        phone='+57-301-987-6543',
        email='dra.garcia@otraclínica.com',
        notes='Cliente frecuente'
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
def another_dest_location():
    """Fixture que crea otra ubicación de destino."""
    return Location.objects.create(
        name='Clínica Sur',
        type='bodega'
    )


@pytest.fixture
def inventory_stock(product, origin_location):
    """Fixture que crea stock de inventario."""
    return InventoryStock.objects.create(
        product=product,
        location=origin_location,
        quantity=100
    )


@pytest.fixture
def sample_deliveries(customer, another_customer, product, origin_location, 
                     dest_location, another_dest_location, inventory_stock):
    """Fixture que crea entregas de muestra para filtros."""
    deliveries = []
    
    # Crear varias ventas
    sale1 = Sale.objects.create(
        customer=customer,
        sale_type='normal',
        should_invoice=True
    )
    SaleItem.objects.create(sale=sale1, product=product, quantity=2, unit_price=Decimal('50000.00'))
    
    sale2 = Sale.objects.create(
        customer=another_customer,
        sale_type='normal',
        should_invoice=True
    )
    SaleItem.objects.create(sale=sale2, product=product, quantity=1, unit_price=Decimal('75000.00'))
    
    sale3 = Sale.objects.create(
        customer=customer,
        sale_type='normal',
        should_invoice=False
    )
    SaleItem.objects.create(sale=sale3, product=product, quantity=3, unit_price=Decimal('30000.00'))
    
    # Crear entregas con diferentes estados y ubicaciones
    now = timezone.now()
    
    # Entrega 1: Pendiente
    delivery1 = Delivery.objects.create(
        sale=sale1,
        origin_location=origin_location,
        dest_location=dest_location,
        status='pending'
    )
    # Modificar created_at para testing de fechas
    delivery1.created_at = now - timedelta(days=3)
    delivery1.save()
    deliveries.append(delivery1)
    
    # Entrega 2: En tránsito
    delivery2 = Delivery.objects.create(
        sale=sale2,
        origin_location=origin_location,
        dest_location=another_dest_location,
        status='in_transit',
        shipped_at=now - timedelta(days=1)
    )
    delivery2.created_at = now - timedelta(days=2)
    delivery2.save()
    deliveries.append(delivery2)
    
    # Entrega 3: Entregada
    delivery3 = Delivery.objects.create(
        sale=sale3,
        origin_location=origin_location,
        dest_location=dest_location,
        status='delivered',
        shipped_at=now - timedelta(days=2),
        delivered_at=now - timedelta(days=1)
    )
    delivery3.created_at = now - timedelta(days=5)
    delivery3.save()
    deliveries.append(delivery3)
    
    return deliveries


# Tests para filtros básicos

@pytest.mark.django_db
def test_filter_by_status(sample_deliveries):
    """Test para filtrar por estado."""
    # Filtrar por pendiente
    filter_set = DeliveryFilter({'status': 'pending'}, queryset=Delivery.objects.all())
    filtered = filter_set.qs
    assert filtered.count() == 1
    assert filtered.first().status == 'pending'
    
    # Filtrar por en tránsito
    filter_set = DeliveryFilter({'status': 'in_transit'}, queryset=Delivery.objects.all())
    filtered = filter_set.qs
    assert filtered.count() == 1
    assert filtered.first().status == 'in_transit'
    
    # Filtrar por entregado
    filter_set = DeliveryFilter({'status': 'delivered'}, queryset=Delivery.objects.all())
    filtered = filter_set.qs
    assert filtered.count() == 1
    assert filtered.first().status == 'delivered'


@pytest.mark.django_db
def test_filter_by_multiple_status(sample_deliveries):
    """Test para filtrar por múltiples estados."""
    filter_set = DeliveryFilter(
        {'status_in': ['pending', 'in_transit']}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2
    statuses = [d.status for d in filtered]
    assert 'pending' in statuses
    assert 'in_transit' in statuses
    assert 'delivered' not in statuses


@pytest.mark.django_db
def test_filter_by_origin_location(sample_deliveries, origin_location):
    """Test para filtrar por ubicación de origen."""
    filter_set = DeliveryFilter(
        {'origin_location': origin_location.id}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 3  # Todas tienen la misma ubicación de origen


@pytest.mark.django_db
def test_filter_by_dest_location(sample_deliveries, dest_location, another_dest_location):
    """Test para filtrar por ubicación de destino."""
    filter_set = DeliveryFilter(
        {'dest_location': dest_location.id}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2  # Dos entregas van a esta ubicación
    
    filter_set = DeliveryFilter(
        {'dest_location': another_dest_location.id}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 1


@pytest.mark.django_db
def test_filter_by_multiple_locations(sample_deliveries, dest_location, another_dest_location):
    """Test para filtrar por múltiples ubicaciones de destino."""
    filter_set = DeliveryFilter(
        {'dest_locations': [dest_location.id, another_dest_location.id]}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 3  # Todas las entregas


# Tests para filtros de cliente

@pytest.mark.django_db
def test_filter_by_customer_name(sample_deliveries):
    """Test para filtrar por nombre del cliente."""
    filter_set = DeliveryFilter(
        {'customer_name': 'Juan'}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2  # Dr. Juan Pérez tiene 2 entregas
    
    filter_set = DeliveryFilter(
        {'customer_name': 'María'}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 1  # Dra. María García tiene 1 entrega


@pytest.mark.django_db
def test_filter_by_customer_email(sample_deliveries):
    """Test para filtrar por email del cliente."""
    filter_set = DeliveryFilter(
        {'customer_email': 'dr.perez'}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2
    
    filter_set = DeliveryFilter(
        {'customer_email': 'otraclínica'}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 1


# Tests para filtros de fecha

@pytest.mark.django_db
def test_filter_by_created_date(sample_deliveries):
    """Test para filtrar por fecha de creación."""
    now = timezone.now()
    
    # Filtrar entregas creadas en los últimos 4 días
    filter_set = DeliveryFilter(
        {'created_after': now - timedelta(days=4)}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2  # No incluye la de hace 5 días
    
    # Filtrar entregas creadas hace más de 1 día
    filter_set = DeliveryFilter(
        {'created_before': now - timedelta(days=1)}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 3  # Todas fueron creadas hace más de 1 día


@pytest.mark.django_db
def test_filter_by_shipped_date(sample_deliveries):
    """Test para filtrar por fecha de envío."""
    now = timezone.now()
    
    # Filtrar entregas enviadas
    filter_set = DeliveryFilter(
        {'shipped_after': now - timedelta(days=3)}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2  # Solo las que tienen fecha de envío


# Tests para filtros booleanos

@pytest.mark.django_db
def test_filter_has_shipped(sample_deliveries):
    """Test para filtrar entregas que han sido enviadas."""
    filter_set = DeliveryFilter(
        {'has_shipped': True}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2  # Solo in_transit y delivered tienen shipped_at
    
    filter_set = DeliveryFilter(
        {'has_shipped': False}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 1  # Solo pending no tiene shipped_at


@pytest.mark.django_db
def test_filter_has_delivered(sample_deliveries):
    """Test para filtrar entregas que han sido entregadas."""
    filter_set = DeliveryFilter(
        {'has_delivered': True}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 1  # Solo delivered tiene delivered_at
    
    filter_set = DeliveryFilter(
        {'has_delivered': False}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2  # pending e in_transit no tienen delivered_at


@pytest.mark.django_db
def test_filter_is_pending(sample_deliveries):
    """Test para filtrar entregas pendientes."""
    filter_set = DeliveryFilter(
        {'is_pending': True}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 1
    assert filtered.first().status == 'pending'
    
    filter_set = DeliveryFilter(
        {'is_pending': False}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2  # in_transit y delivered


@pytest.mark.django_db
def test_filter_is_overdue(sample_deliveries):
    """Test para filtrar entregas atrasadas."""
    # Por defecto, overdue son entregas de más de 7 días sin entregar
    # Nuestras entregas son de máximo 5 días, así que modificamos una
    
    now = timezone.now()
    old_delivery = sample_deliveries[0]  # La pendiente
    old_delivery.created_at = now - timedelta(days=10)
    old_delivery.save()
    
    filter_set = DeliveryFilter(
        {'is_overdue': True}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 1
    assert filtered.first() == old_delivery
    
    filter_set = DeliveryFilter(
        {'is_overdue': False}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2


# Tests para filtros de venta

@pytest.mark.django_db
def test_filter_by_sale_id(sample_deliveries):
    """Test para filtrar por ID de venta."""
    delivery = sample_deliveries[0]
    filter_set = DeliveryFilter(
        {'sale_id': delivery.sale.id}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 1
    assert filtered.first() == delivery


@pytest.mark.django_db
def test_filter_by_sale_total(sample_deliveries):
    """Test para filtrar por total de venta."""
    # Filtrar ventas con total mayor a 70000
    filter_set = DeliveryFilter(
        {'sale_total_min': 70000}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() >= 1  # Al menos una venta supera este monto
    
    # Filtrar ventas con total menor a 100000
    filter_set = DeliveryFilter(
        {'sale_total_max': 100000}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() >= 1


# Tests para búsqueda general

@pytest.mark.django_db
def test_general_search(sample_deliveries):
    """Test para búsqueda general."""
    # Buscar por nombre de cliente
    filter_set = DeliveryFilter(
        {'search': 'Juan'}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2
    
    # Buscar por ubicación
    filter_set = DeliveryFilter(
        {'search': 'Norte'}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 2  # Dos entregas van a "Clínica Norte"
    
    # Buscar por estado
    filter_set = DeliveryFilter(
        {'search': 'pending'}, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 1


# Tests para combinación de filtros

@pytest.mark.django_db
def test_combined_filters(sample_deliveries, dest_location):
    """Test para combinación de filtros."""
    filter_set = DeliveryFilter(
        {
            'status': 'pending',
            'dest_location': dest_location.id,
            'customer_name': 'Juan'
        }, 
        queryset=Delivery.objects.all()
    )
    filtered = filter_set.qs
    assert filtered.count() == 1  # Solo una entrega cumple todos los criterios


@pytest.mark.django_db
def test_empty_filters(sample_deliveries):
    """Test para filtros vacíos."""
    filter_set = DeliveryFilter({}, queryset=Delivery.objects.all())
    filtered = filter_set.qs
    assert filtered.count() == 3  # Todas las entregas sin filtros 
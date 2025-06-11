import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from deliveries.models import Delivery
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
def sale(customer, product, inventory_stock, origin_location):
    """Fixture que crea una venta de muestra."""
    sale = Sale.objects.create(
        customer=customer,
        location=origin_location,  # Agregar ubicación requerida
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
def delivery_data(sale, origin_location, dest_location):
    """Fixture con datos de muestra para crear entregas."""
    return {
        'sale': sale,
        'origin_location': origin_location,
        'dest_location': dest_location,
        'status': 'pending'
    }


# Tests para el modelo Delivery

@pytest.mark.django_db
def test_create_delivery_with_all_fields(delivery_data):
    """Test para crear una entrega con todos los campos."""
    delivery = Delivery.objects.create(**delivery_data)
    
    assert delivery.id is not None
    assert delivery.sale == delivery_data['sale']
    assert delivery.origin_location == delivery_data['origin_location']
    assert delivery.dest_location == delivery_data['dest_location']
    assert delivery.status == 'pending'
    assert delivery.shipped_at is None
    assert delivery.delivered_at is None
    assert delivery.created_at is not None
    assert delivery.updated_at is not None


@pytest.mark.django_db
def test_delivery_str_representation(delivery_data):
    """Test para la representación string de la entrega."""
    delivery = Delivery.objects.create(**delivery_data)
    expected = f"Entrega #{delivery.id} - Venta #{delivery.sale.id} - Pendiente"
    assert str(delivery) == expected


@pytest.mark.django_db
def test_delivery_ordering(sale, origin_location, dest_location):
    """Test para verificar el ordenamiento por defecto de entregas."""
    # Crear entregas en diferentes momentos
    delivery1 = Delivery.objects.create(
        sale=sale,
        origin_location=origin_location,
        dest_location=dest_location
    )
    
    # Necesitamos crear otra venta para la segunda entrega
    sale2 = Sale.objects.create(
        customer=sale.customer,
        location=origin_location,  # Agregar ubicación requerida
        sale_type='normal',
        should_invoice=True
    )
    
    delivery2 = Delivery.objects.create(
        sale=sale2,
        origin_location=origin_location,
        dest_location=dest_location
    )
    
    deliveries = list(Delivery.objects.all())
    # Debe estar ordenado por created_at descendente (más reciente primero)
    assert deliveries[0] == delivery2
    assert deliveries[1] == delivery1


@pytest.mark.django_db
def test_mark_as_shipped(delivery_data):
    """Test para marcar una entrega como enviada."""
    delivery = Delivery.objects.create(**delivery_data)
    
    delivery.mark_as_shipped()
    
    assert delivery.status == 'in_transit'
    assert delivery.shipped_at is not None
    assert delivery.delivered_at is None


@pytest.mark.django_db
def test_mark_as_delivered(delivery_data):
    """Test para marcar una entrega como entregada."""
    delivery = Delivery.objects.create(**delivery_data)
    
    delivery.mark_as_delivered()
    
    assert delivery.status == 'delivered'
    assert delivery.shipped_at is not None
    assert delivery.delivered_at is not None


@pytest.mark.django_db
def test_mark_as_shipped_invalid_state(delivery_data):
    """Test para verificar que no se puede enviar una entrega que no está pendiente."""
    delivery = Delivery.objects.create(**delivery_data)
    delivery.mark_as_delivered()  # Primero la marcamos como entregada
    
    with pytest.raises(ValidationError):
        delivery.mark_as_shipped()


@pytest.mark.django_db
def test_mark_as_delivered_invalid_state(delivery_data):
    """Test para verificar estados válidos para marcar como entregado."""
    delivery = Delivery.objects.create(**delivery_data)
    delivery.mark_as_delivered()  # Primero la marcamos como entregada
    
    with pytest.raises(ValidationError):
        delivery.mark_as_delivered()  # Intentar marcarla de nuevo como entregada


@pytest.mark.django_db
def test_can_be_modified_pending(delivery_data):
    """Test para verificar que entregas pendientes pueden ser modificadas."""
    delivery = Delivery.objects.create(**delivery_data)
    assert delivery.can_be_modified() is True


@pytest.mark.django_db
def test_can_be_modified_in_transit(delivery_data):
    """Test para verificar que entregas en tránsito no pueden ser modificadas."""
    delivery = Delivery.objects.create(**delivery_data)
    delivery.mark_as_shipped()
    assert delivery.can_be_modified() is False


@pytest.mark.django_db
def test_can_be_modified_delivered(delivery_data):
    """Test para verificar que entregas entregadas no pueden ser modificadas."""
    delivery = Delivery.objects.create(**delivery_data)
    delivery.mark_as_delivered()
    assert delivery.can_be_modified() is False


@pytest.mark.django_db
def test_status_check_methods(delivery_data):
    """Test para los métodos de verificación de estado."""
    delivery = Delivery.objects.create(**delivery_data)
    
    # Estado inicial: pending
    assert delivery.is_pending() is True
    assert delivery.is_in_transit() is False
    assert delivery.is_delivered() is False
    
    # Estado: in_transit
    delivery.mark_as_shipped()
    assert delivery.is_pending() is False
    assert delivery.is_in_transit() is True
    assert delivery.is_delivered() is False
    
    # Estado: delivered
    delivery.mark_as_delivered()
    assert delivery.is_pending() is False
    assert delivery.is_in_transit() is False
    assert delivery.is_delivered() is True


@pytest.mark.django_db
def test_delivery_time_property(delivery_data):
    """Test para la propiedad delivery_time."""
    delivery = Delivery.objects.create(**delivery_data)
    
    # Sin fechas
    assert delivery.delivery_time is None
    
    # Con fechas (mismo día)
    now = timezone.now()
    delivery.shipped_at = now
    delivery.delivered_at = now
    delivery.save()
    
    assert delivery.delivery_time == 0
    
    # Con diferencia de 2 días
    delivery.delivered_at = now + timedelta(days=2)
    delivery.save()
    
    assert delivery.delivery_time == 2


@pytest.mark.django_db
def test_customer_name_property(delivery_data):
    """Test para la propiedad customer_name."""
    delivery = Delivery.objects.create(**delivery_data)
    assert delivery.customer_name == delivery.sale.customer.name


@pytest.mark.django_db
def test_customer_name_anonymous(delivery_data):
    """Test para customer_name con venta anónima."""
    delivery_data['sale'].customer = None
    delivery_data['sale'].save()
    
    delivery = Delivery.objects.create(**delivery_data)
    assert delivery.customer_name == "Cliente Anónimo"


@pytest.mark.django_db
def test_sale_total_property(delivery_data):
    """Test para la propiedad sale_total."""
    delivery = Delivery.objects.create(**delivery_data)
    assert delivery.sale_total == delivery.sale.total_gross


@pytest.mark.django_db
def test_delivery_validation_shipped_before_delivered(delivery_data):
    """Test para validar que shipped_at no puede ser posterior a delivered_at."""
    delivery = Delivery(**delivery_data)
    now = timezone.now()
    delivery.shipped_at = now
    delivery.delivered_at = now - timedelta(hours=1)  # 1 hora antes
    
    with pytest.raises(ValidationError):
        delivery.full_clean()


@pytest.mark.django_db
def test_delivery_validation_in_transit_requires_shipped_at(delivery_data):
    """Test para validar que estado 'in_transit' requiere shipped_at."""
    delivery = Delivery(**delivery_data)
    delivery.status = 'in_transit'
    
    with pytest.raises(ValidationError):
        delivery.full_clean()


@pytest.mark.django_db
def test_delivery_validation_delivered_requires_delivered_at(delivery_data):
    """Test para validar que estado 'delivered' requiere delivered_at."""
    delivery = Delivery(**delivery_data)
    delivery.status = 'delivered'
    
    with pytest.raises(ValidationError):
        delivery.full_clean()


@pytest.mark.django_db
def test_delivery_validation_delivered_at_requires_shipped_at(delivery_data):
    """Test para validar que delivered_at requiere shipped_at."""
    delivery = Delivery(**delivery_data)
    delivery.delivered_at = timezone.now()
    
    with pytest.raises(ValidationError):
        delivery.full_clean()


@pytest.mark.django_db
def test_delivery_cascade_delete_sale(delivery_data):
    """Test para verificar que eliminar la venta elimina la entrega."""
    delivery = Delivery.objects.create(**delivery_data)
    sale_id = delivery.sale.id
    
    delivery.sale.delete()
    
    with pytest.raises(Delivery.DoesNotExist):
        Delivery.objects.get(sale_id=sale_id)


@pytest.mark.django_db
def test_delivery_protect_location_delete(delivery_data):
    """Test para verificar que no se puede eliminar una ubicación con entregas."""
    from django.db import IntegrityError
    
    delivery = Delivery.objects.create(**delivery_data)
    
    # No debería poder eliminar la ubicación de origen
    with pytest.raises(IntegrityError):
        delivery.origin_location.delete()
    
    # No debería poder eliminar la ubicación de destino
    with pytest.raises(IntegrityError):
        delivery.dest_location.delete()


@pytest.mark.django_db
def test_delivery_one_to_one_sale_constraint(delivery_data, dest_location):
    """Test para verificar que una venta solo puede tener una entrega."""
    from django.core.exceptions import ValidationError
    
    # Crear primera entrega
    Delivery.objects.create(**delivery_data)
    
    # Intentar crear segunda entrega para la misma venta
    with pytest.raises(ValidationError):
        delivery2 = Delivery(
            sale=delivery_data['sale'],
            origin_location=delivery_data['origin_location'],
            dest_location=dest_location,
            status='pending'
        )
        delivery2.full_clean() 
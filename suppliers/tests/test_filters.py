import pytest
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from suppliers.models import Supplier, PurchaseOption
from suppliers.filters import SupplierFilter, PurchaseOptionFilter
from catalogs.models import Category, Product


@pytest.fixture
def suppliers():
    """
    Fixture que crea proveedores de muestra.
    """
    supplier1 = Supplier.objects.create(
        name='Dental Supplies Co.',
        contact_name='Juan Pérez',
        phone='+1-555-0123',
        email='juan@dentalsupplies.com'
    )
    
    supplier2 = Supplier.objects.create(
        name='Medical Equipment Ltd.',
        contact_name='María García',
        phone='+1-555-0456', 
        email='maria@medicalequip.com'
    )
    
    supplier3 = Supplier.objects.create(
        name='Global Dental Corp.',
        contact_name='Carlos López',
        phone='+1-555-0789',
        email='carlos@globaldental.com'
    )
    
    return [supplier1, supplier2, supplier3]


@pytest.fixture
def purchase_option_test_data():
    """
    Fixture que crea datos completos para tests de PurchaseOption.
    """
    # Crear datos base
    category1 = Category.objects.create(
        name='Instrumental Dental',
        description='Herramientas dentales'
    )
    
    category2 = Category.objects.create(
        name='Materiales',
        description='Materiales dentales'
    )
    
    product1 = Product.objects.create(
        sku='INS-DEN-JER-001',
        name='Jeringa Dental',
        description='Jeringa para procedimientos',
        unit='unidad',
        category=category1
    )
    
    product2 = Product.objects.create(
        sku='MAT-DEN-AMA-001',
        name='Amalgama Silver',
        description='Material de amalgama',
        unit='caja',
        category=category2
    )
    
    supplier1 = Supplier.objects.create(
        name='Dental Supplies Inc.',
        contact_name='Juan Pérez',
        email='juan@dental.com'
    )
    
    supplier2 = Supplier.objects.create(
        name='Medical Tools Ltd.',
        contact_name='María García',
        email='maria@medical.com'
    )
    
    # Crear opciones de compra
    option1 = PurchaseOption.objects.create(
        product=product1,
        supplier=supplier1,
        brand='DentalTech Pro',
        purchase_price=Decimal('20.00'),
        valid_from=date.today() - timedelta(days=30),
        valid_to=date.today() + timedelta(days=60)
    )
    
    option2 = PurchaseOption.objects.create(
        product=product2,
        supplier=supplier2,
        brand='Silver Max',
        purchase_price=Decimal('35.00'),
        valid_from=date.today(),
        valid_to=date.today() + timedelta(days=90)
    )
    
    option3 = PurchaseOption.objects.create(
        product=product1,
        supplier=supplier2,
        brand='MediCare',
        purchase_price=Decimal('18.50'),
        valid_from=date.today() + timedelta(days=10)
    )
    
    # Opción expirada
    option4 = PurchaseOption.objects.create(
        product=product2,
        supplier=supplier1,
        brand='Old Brand',
        purchase_price=Decimal('40.00'),
        valid_from=date.today() - timedelta(days=100),
        valid_to=date.today() - timedelta(days=10)
    )
    
    return {
        'categories': [category1, category2],
        'products': [product1, product2],
        'suppliers': [supplier1, supplier2],
        'options': [option1, option2, option3, option4]
    }


# Tests para SupplierFilter

@pytest.mark.django_db
def test_filter_suppliers_by_name(suppliers):
    """
    Test para filtrar proveedores por nombre.
    """
    filter_set = SupplierFilter(data={'name': 'Dental'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    supplier_names = [s.name for s in filtered_qs]
    assert 'Dental Supplies Co.' in supplier_names
    assert 'Global Dental Corp.' in supplier_names
    assert 'Medical Equipment Ltd.' not in supplier_names


@pytest.mark.django_db
def test_filter_suppliers_by_contact_name(suppliers):
    """
    Test para filtrar proveedores por nombre de contacto.
    """
    filter_set = SupplierFilter(data={'contact_name': 'Juan'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 1
    assert filtered_qs.first() == suppliers[0]


@pytest.mark.django_db
def test_filter_suppliers_by_email(suppliers):
    """
    Test para filtrar proveedores por email.
    """
    filter_set = SupplierFilter(data={'email': 'dentalsupplies'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 1
    assert filtered_qs.first() == suppliers[0]


@pytest.mark.django_db
def test_filter_suppliers_by_phone(suppliers):
    """
    Test para filtrar proveedores por teléfono.
    """
    filter_set = SupplierFilter(data={'phone': '0456'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 1
    assert filtered_qs.first() == suppliers[1]


@pytest.mark.django_db
def test_filter_suppliers_multiple_fields(suppliers):
    """
    Test para filtrar proveedores por múltiples campos.
    """
    filter_set = SupplierFilter(data={
        'name': 'Dental',
        'contact_name': 'Juan'
    })
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 1
    assert filtered_qs.first() == suppliers[0]


@pytest.mark.django_db
def test_filter_suppliers_case_insensitive(suppliers):
    """
    Test para verificar que los filtros son case-insensitive.
    """
    filter_set = SupplierFilter(data={'name': 'dental'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    supplier_names = [s.name for s in filtered_qs]
    assert 'Dental Supplies Co.' in supplier_names
    assert 'Global Dental Corp.' in supplier_names


@pytest.mark.django_db
def test_filter_suppliers_no_results(suppliers):
    """
    Test para filtrar sin resultados.
    """
    filter_set = SupplierFilter(data={'name': 'NonExistent'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 0


@pytest.mark.django_db
def test_filter_suppliers_empty_data(suppliers):
    """
    Test para filtro sin datos (debería retornar todos).
    """
    filter_set = SupplierFilter(data={})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 3


# Tests para PurchaseOptionFilter

@pytest.mark.django_db
def test_filter_purchase_options_by_product_id(purchase_option_test_data):
    """
    Test para filtrar por ID de producto.
    """
    product1 = purchase_option_test_data['products'][0]
    filter_set = PurchaseOptionFilter(data={'product': product1.id})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    product_ids = [o.product.id for o in filtered_qs]
    assert all(pid == product1.id for pid in product_ids)


@pytest.mark.django_db
def test_filter_purchase_options_by_product_name(purchase_option_test_data):
    """
    Test para filtrar por nombre de producto.
    """
    product1 = purchase_option_test_data['products'][0]
    filter_set = PurchaseOptionFilter(data={'product_name': 'Jeringa'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    assert all(o.product == product1 for o in filtered_qs)


@pytest.mark.django_db
def test_filter_purchase_options_by_supplier_id(purchase_option_test_data):
    """
    Test para filtrar por ID de proveedor.
    """
    supplier1 = purchase_option_test_data['suppliers'][0]
    filter_set = PurchaseOptionFilter(data={'supplier': supplier1.id})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    supplier_ids = [o.supplier.id for o in filtered_qs]
    assert all(sid == supplier1.id for sid in supplier_ids)


@pytest.mark.django_db
def test_filter_purchase_options_by_supplier_name(purchase_option_test_data):
    """
    Test para filtrar por nombre de proveedor.
    """
    supplier1 = purchase_option_test_data['suppliers'][0]
    filter_set = PurchaseOptionFilter(data={'supplier_name': 'Dental'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    assert all(o.supplier == supplier1 for o in filtered_qs)


@pytest.mark.django_db
def test_filter_purchase_options_by_brand(purchase_option_test_data):
    """
    Test para filtrar por marca.
    """
    option1 = purchase_option_test_data['options'][0]
    filter_set = PurchaseOptionFilter(data={'brand': 'DentalTech'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 1
    assert filtered_qs.first() == option1


@pytest.mark.django_db
def test_filter_purchase_options_by_category_id(purchase_option_test_data):
    """
    Test para filtrar por ID de categoría.
    """
    category1 = purchase_option_test_data['categories'][0]
    filter_set = PurchaseOptionFilter(data={'category': category1.id})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    category_ids = [o.product.category.id for o in filtered_qs]
    assert all(cid == category1.id for cid in category_ids)


@pytest.mark.django_db
def test_filter_purchase_options_by_category_name(purchase_option_test_data):
    """
    Test para filtrar por nombre de categoría.
    """
    category1 = purchase_option_test_data['categories'][0]
    filter_set = PurchaseOptionFilter(data={'category_name': 'Instrumental'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    assert all(o.product.category == category1 for o in filtered_qs)


@pytest.mark.django_db
def test_filter_purchase_options_by_min_price(purchase_option_test_data):
    """
    Test para filtrar por precio mínimo.
    """
    filter_set = PurchaseOptionFilter(data={'min_price': 30})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    prices = [o.purchase_price for o in filtered_qs]
    assert all(price >= Decimal('30.00') for price in prices)


@pytest.mark.django_db
def test_filter_purchase_options_by_max_price(purchase_option_test_data):
    """
    Test para filtrar por precio máximo.
    """
    filter_set = PurchaseOptionFilter(data={'max_price': 25})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    prices = [o.purchase_price for o in filtered_qs]
    assert all(price <= Decimal('25.00') for price in prices)


@pytest.mark.django_db
def test_filter_purchase_options_by_price_range(purchase_option_test_data):
    """
    Test para filtrar por rango de precio.
    """
    filter_set = PurchaseOptionFilter(data={
        'min_price': 18,
        'max_price': 25
    })
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    prices = [o.purchase_price for o in filtered_qs]
    assert all(Decimal('18.00') <= price <= Decimal('25.00') for price in prices)


@pytest.mark.django_db
def test_filter_purchase_options_by_valid_from_start(purchase_option_test_data):
    """
    Test para filtrar por fecha de inicio de validez.
    """
    today = date.today()
    filter_set = PurchaseOptionFilter(data={'valid_from_start': today})
    filtered_qs = filter_set.qs
    
    # Debe incluir opciones que empiezan hoy o después
    valid_options = [o for o in filtered_qs if o.valid_from >= today]
    assert len(valid_options) == filtered_qs.count()


@pytest.mark.django_db
def test_filter_purchase_options_by_valid_from_end(purchase_option_test_data):
    """
    Test para filtrar por fecha de fin de inicio de validez.
    """
    yesterday = date.today() - timedelta(days=1)
    filter_set = PurchaseOptionFilter(data={'valid_from_end': yesterday})
    filtered_qs = filter_set.qs
    
    # Debe incluir opciones que empezaron ayer o antes
    valid_options = [o for o in filtered_qs if o.valid_from <= yesterday]
    assert len(valid_options) == filtered_qs.count()


@pytest.mark.django_db
def test_filter_purchase_options_currently_valid_true(purchase_option_test_data):
    """
    Test para filtrar opciones actualmente válidas.
    """
    option4 = purchase_option_test_data['options'][3]  # Opción expirada
    filter_set = PurchaseOptionFilter(data={'is_currently_valid': True})
    filtered_qs = filter_set.qs
    
    # Verificar que todas las opciones retornadas están válidas
    today = timezone.localdate()
    for option in filtered_qs:
        assert option.valid_from <= today
        if option.valid_to:
            assert option.valid_to >= today
    
    # No debe incluir la opción expirada
    option_ids = [o.id for o in filtered_qs]
    assert option4.id not in option_ids


@pytest.mark.django_db
def test_filter_purchase_options_currently_valid_false(purchase_option_test_data):
    """
    Test para filtrar opciones NO válidas actualmente.
    """
    option3 = purchase_option_test_data['options'][2]  # Opción futura
    option4 = purchase_option_test_data['options'][3]  # Opción expirada
    
    filter_set = PurchaseOptionFilter(data={'is_currently_valid': False})
    filtered_qs = filter_set.qs
    
    # Debe incluir la opción expirada y la opción futura
    option_ids = [o.id for o in filtered_qs]
    assert option4.id in option_ids  # Expirada
    assert option3.id in option_ids  # Futura


@pytest.mark.django_db
def test_filter_purchase_options_multiple_criteria(purchase_option_test_data):
    """
    Test para filtrar con múltiples criterios.
    """
    option1 = purchase_option_test_data['options'][0]
    filter_set = PurchaseOptionFilter(data={
        'product_name': 'Jeringa',
        'supplier_name': 'Dental',
        'min_price': 18,
        'max_price': 25
    })
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 1
    assert filtered_qs.first() == option1


@pytest.mark.django_db
def test_filter_purchase_options_valid_to_date_range(purchase_option_test_data):
    """
    Test para filtrar por rango de fechas de vencimiento.
    """
    future_date = date.today() + timedelta(days=30)
    filter_set = PurchaseOptionFilter(data={'valid_to_start': future_date})
    filtered_qs = filter_set.qs
    
    # Solo opciones que vencen después de future_date
    for option in filtered_qs:
        if option.valid_to:
            assert option.valid_to >= future_date


@pytest.mark.django_db
def test_filter_purchase_options_brand_case_insensitive(purchase_option_test_data):
    """
    Test para verificar que el filtro de marca es case-insensitive.
    """
    option1 = purchase_option_test_data['options'][0]
    filter_set = PurchaseOptionFilter(data={'brand': 'dentaltech'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 1
    assert filtered_qs.first() == option1


@pytest.mark.django_db
def test_filter_purchase_options_no_results(purchase_option_test_data):
    """
    Test para filtro que no retorna resultados.
    """
    filter_set = PurchaseOptionFilter(data={'brand': 'NonExistentBrand'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 0


@pytest.mark.django_db
def test_filter_purchase_options_empty_data(purchase_option_test_data):
    """
    Test para filtro sin datos (debería retornar todas las opciones).
    """
    filter_set = PurchaseOptionFilter(data={})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 4


@pytest.mark.django_db
def test_filter_purchase_options_valid_options_with_null_valid_to(purchase_option_test_data):
    """
    Test para verificar filtrado de opciones válidas con valid_to = NULL.
    """
    option3 = purchase_option_test_data['options'][2]  # No tiene valid_to pero empieza en el futuro
    filter_set = PurchaseOptionFilter(data={'is_currently_valid': True})
    filtered_qs = filter_set.qs
    
    option_ids = [o.id for o in filtered_qs]
    assert option3.id not in option_ids  # No está válida ahora (empieza en el futuro)


@pytest.mark.django_db
def test_filter_purchase_options_combination_with_ordering(purchase_option_test_data):
    """
    Test para verificar que los filtros funcionan con el QuerySet ordenado.
    """
    # El QuerySet tiene ordering por defecto
    filter_set = PurchaseOptionFilter(data={'category_name': 'Instrumental'})
    filtered_qs = filter_set.qs
    
    assert filtered_qs.count() == 2
    # Verificar que mantiene el orden
    options = list(filtered_qs)
    assert len(options) == 2 
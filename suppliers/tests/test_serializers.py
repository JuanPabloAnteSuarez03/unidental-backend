import pytest
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from datetime import date, timedelta
from decimal import Decimal

from suppliers.models import Supplier, PurchaseOption
from suppliers.serializers import (
    SupplierSerializer, 
    SupplierDetailSerializer,
    PurchaseOptionSerializer, 
    PurchaseOptionDetailSerializer
)
from catalogs.models import Category, Product


@pytest.fixture
def supplier_data():
    """
    Fixture con datos de muestra para crear proveedores.
    """
    return {
        'name': 'Test Supplier',
        'contact_name': 'John Doe',
        'phone': '+1-555-0123',
        'email': 'test@supplier.com'
    }


@pytest.fixture
def supplier(supplier_data):
    """
    Fixture que crea un proveedor de muestra.
    """
    return Supplier.objects.create(**supplier_data)


@pytest.fixture
def category():
    """
    Fixture que crea una categoría de muestra.
    """
    return Category.objects.create(
        name='Instrumental Dental',
        description='Herramientas dentales'
    )


@pytest.fixture
def product(category):
    """
    Fixture que crea un producto de muestra.
    """
    return Product.objects.create(
        sku='INS-DEN-JER-001',
        name='Jeringa Dental',
        description='Jeringa para procedimientos dentales',
        unit='unidad',
        category=category
    )


@pytest.fixture
def purchase_option_data(product, supplier):
    """
    Fixture con datos de muestra para crear opciones de compra.
    """
    return {
        'product': product.id,
        'supplier': supplier.id,
        'brand': 'Test Brand',
        'purchase_price': '15.50',
        'valid_from': date.today(),
        'valid_to': date.today() + timedelta(days=90)
    }


@pytest.fixture
def purchase_option(product, supplier):
    """
    Fixture que crea una opción de compra de muestra.
    """
    return PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='DentalTech',
        purchase_price=Decimal('20.00'),
        valid_from=date.today(),
        valid_to=date.today() + timedelta(days=90)
    )


# Tests para SupplierSerializer

@pytest.mark.django_db
def test_serialize_supplier(supplier, supplier_data):
    """
    Test para serializar un proveedor.
    """
    serializer = SupplierSerializer(supplier)
    data = serializer.data
    
    assert data['id'] == supplier.id
    assert data['name'] == supplier.name
    assert data['contact_name'] == supplier.contact_name
    assert data['phone'] == supplier.phone
    assert data['email'] == supplier.email
    assert 'created_at' in data
    assert 'updated_at' in data


@pytest.mark.django_db
def test_deserialize_valid_supplier():
    """
    Test para deserializar datos válidos de proveedor.
    """
    data = {
        'name': 'New Supplier',
        'contact_name': 'New Contact',
        'phone': '+1-555-9999',
        'email': 'new@supplier.com'
    }
    
    serializer = SupplierSerializer(data=data)
    assert serializer.is_valid()
    supplier = serializer.save()
    
    assert supplier.name == data['name']
    assert supplier.contact_name == data['contact_name']
    assert supplier.phone == data['phone']
    assert supplier.email == data['email']


@pytest.mark.django_db
def test_deserialize_supplier_minimal_data():
    """
    Test para deserializar datos mínimos de proveedor.
    """
    data = {'name': 'Minimal Supplier'}
    
    serializer = SupplierSerializer(data=data)
    assert serializer.is_valid()
    supplier = serializer.save()
    
    assert supplier.name == 'Minimal Supplier'
    assert supplier.contact_name is None
    assert supplier.phone is None
    assert supplier.email is None


@pytest.mark.django_db
def test_deserialize_invalid_supplier():
    """
    Test para deserializar datos inválidos de proveedor.
    """
    # Sin nombre (campo requerido)
    data = {
        'contact_name': 'Test Contact',
        'email': 'invalid-email'  # Email inválido
    }
    
    serializer = SupplierSerializer(data=data)
    assert not serializer.is_valid()
    assert 'name' in serializer.errors
    assert 'email' in serializer.errors


@pytest.mark.django_db
def test_update_supplier(supplier):
    """
    Test para actualizar un proveedor.
    """
    data = {
        'name': 'Updated Supplier',
        'contact_name': 'Updated Contact',
        'phone': '+1-555-8888',
        'email': 'updated@supplier.com'
    }
    
    serializer = SupplierSerializer(supplier, data=data)
    assert serializer.is_valid()
    updated_supplier = serializer.save()
    
    assert updated_supplier.name == 'Updated Supplier'
    assert updated_supplier.contact_name == 'Updated Contact'
    assert updated_supplier.phone == '+1-555-8888'
    assert updated_supplier.email == 'updated@supplier.com'


@pytest.mark.django_db
def test_partial_update_supplier(supplier):
    """
    Test para actualizar parcialmente un proveedor.
    """
    original_contact = supplier.contact_name
    data = {'name': 'Partially Updated Supplier'}
    
    serializer = SupplierSerializer(supplier, data=data, partial=True)
    assert serializer.is_valid()
    updated_supplier = serializer.save()
    
    assert updated_supplier.name == 'Partially Updated Supplier'
    assert updated_supplier.contact_name == original_contact  # No debe cambiar


@pytest.mark.django_db
def test_read_only_fields(supplier):
    """
    Test para verificar que los campos read-only no se pueden modificar.
    """
    original_id = supplier.id
    original_created_at = supplier.created_at
    
    data = {
        'id': 999,  # Intentar cambiar ID
        'name': 'Updated Name',
        'created_at': '2020-01-01T00:00:00Z',  # Intentar cambiar created_at
        'updated_at': '2020-01-01T00:00:00Z'   # Intentar cambiar updated_at
    }
    
    serializer = SupplierSerializer(supplier, data=data)
    assert serializer.is_valid()
    updated_supplier = serializer.save()
    
    # Verificar que los campos read-only no cambiaron
    assert updated_supplier.id == original_id
    assert updated_supplier.created_at == original_created_at
    assert updated_supplier.name == 'Updated Name'  # Este sí debe cambiar


@pytest.mark.django_db
def test_serialize_supplier_with_purchase_options(supplier, product):
    """
    Test para serializar un proveedor con opciones de compra.
    """
    # Crear algunas opciones de compra
    PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Brand A',
        purchase_price=Decimal('15.00'),
        valid_from=date.today()
    )
    
    PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Brand B',
        purchase_price=Decimal('18.00'),
        valid_from=date.today()
    )
    
    serializer = SupplierSerializer(supplier)
    data = serializer.data
    
    # El serializer base no incluye purchase_options,
    # pero podemos verificar que el proveedor está correctamente serializado
    assert data['name'] == supplier.name
    assert supplier.purchase_options.count() == 2


# Tests para SupplierDetailSerializer

@pytest.mark.django_db
def test_serialize_supplier_with_purchase_options(supplier, category, product):
    """
    Test para serializar proveedor con opciones de compra.
    """
    purchase_option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Test Brand',
        purchase_price=Decimal('8.00'),
        valid_from=date.today()
    )
    
    serializer = SupplierDetailSerializer(supplier)
    data = serializer.data
    
    # Campos básicos del proveedor
    assert data['id'] == supplier.id
    assert data['name'] == supplier.name
    assert data['contact_name'] == supplier.contact_name
    assert data['email'] == supplier.email
    
    # Opciones de compra incluidas
    assert 'purchase_options' in data
    assert len(data['purchase_options']) == 1
    
    option_data = data['purchase_options'][0]
    assert option_data['id'] == purchase_option.id
    assert option_data['brand'] == 'Test Brand'
    assert option_data['product'] == product.id
    assert option_data['product_name'] == product.name


@pytest.mark.django_db
def test_serialize_supplier_without_purchase_options():
    """
    Test para serializar proveedor sin opciones de compra.
    """
    empty_supplier = Supplier.objects.create(
        name='Empty Supplier',
        email='empty@supplier.com'
    )
    
    serializer = SupplierDetailSerializer(empty_supplier)
    data = serializer.data
    
    assert data['name'] == 'Empty Supplier'
    assert 'purchase_options' in data
    assert len(data['purchase_options']) == 0


# Tests para PurchaseOptionSerializer

@pytest.mark.django_db
def test_serialize_purchase_option(purchase_option):
    """
    Test para serializar una opción de compra.
    """
    serializer = PurchaseOptionSerializer(purchase_option)
    data = serializer.data
    
    assert data['id'] == purchase_option.id
    assert data['product'] == purchase_option.product.id
    assert data['product_name'] == purchase_option.product.name
    assert data['supplier'] == purchase_option.supplier.id
    assert data['supplier_name'] == purchase_option.supplier.name
    assert data['category_name'] == purchase_option.product.category.name
    assert data['brand'] == purchase_option.brand
    assert Decimal(data['purchase_price']) == purchase_option.purchase_price
    assert data['valid_from'] == purchase_option.valid_from.isoformat()
    assert data['valid_to'] == purchase_option.valid_to.isoformat()
    assert data['is_currently_valid'] is True
    assert 'created_at' in data


@pytest.mark.django_db
def test_deserialize_valid_purchase_option(product, supplier):
    """
    Test para deserializar datos válidos de opción de compra.
    """
    data = {
        'product': product.id,
        'supplier': supplier.id,
        'brand': 'Test Brand',
        'purchase_price': '25.50',
        'valid_from': date.today().isoformat(),
        'valid_to': (date.today() + timedelta(days=60)).isoformat()
    }
    
    serializer = PurchaseOptionSerializer(data=data)
    assert serializer.is_valid()
    option = serializer.save()
    
    assert option.product == product
    assert option.supplier == supplier
    assert option.brand == 'Test Brand'
    assert option.purchase_price == Decimal('25.50')


@pytest.mark.django_db
def test_deserialize_without_valid_to(product, supplier):
    """
    Test para deserializar opción de compra sin fecha de vencimiento.
    """
    data = {
        'product': product.id,
        'supplier': supplier.id,
        'brand': 'No Expiry Brand',
        'purchase_price': '15.00',
        'valid_from': date.today().isoformat()
    }
    
    serializer = PurchaseOptionSerializer(data=data)
    assert serializer.is_valid()
    option = serializer.save()
    
    assert option.valid_to is None


@pytest.mark.django_db
def test_deserialize_invalid_supplier(product):
    """
    Test para deserializar con proveedor inválido.
    """
    data = {
        'product': product.id,
        'supplier': 999,  # ID inexistente
        'brand': 'Test Brand',
        'purchase_price': '15.00',
        'valid_from': date.today().isoformat()
    }
    
    serializer = PurchaseOptionSerializer(data=data)
    assert not serializer.is_valid()
    assert 'supplier' in serializer.errors


@pytest.mark.django_db
def test_deserialize_invalid_price(product, supplier):
    """
    Test para deserializar con precio inválido.
    """
    data = {
        'product': product.id,
        'supplier': supplier.id,
        'brand': 'Test Brand',
        'purchase_price': 'invalid_price',
        'valid_from': date.today().isoformat()
    }
    
    serializer = PurchaseOptionSerializer(data=data)
    assert not serializer.is_valid()
    assert 'purchase_price' in serializer.errors


@pytest.mark.django_db
def test_update_purchase_option(purchase_option, product, supplier):
    """
    Test para actualizar una opción de compra.
    """
    data = {
        'product': product.id,
        'supplier': supplier.id,
        'brand': 'Updated Brand',
        'purchase_price': '30.00',
        'valid_from': date.today().isoformat(),
        'valid_to': (date.today() + timedelta(days=120)).isoformat()
    }
    
    serializer = PurchaseOptionSerializer(purchase_option, data=data)
    assert serializer.is_valid()
    updated_option = serializer.save()
    
    assert updated_option.brand == 'Updated Brand'
    assert updated_option.purchase_price == Decimal('30.00')


@pytest.mark.django_db
def test_partial_update_purchase_option(purchase_option):
    """
    Test para actualizar parcialmente una opción de compra.
    """
    original_brand = purchase_option.brand
    data = {'purchase_price': '22.00'}
    
    serializer = PurchaseOptionSerializer(purchase_option, data=data, partial=True)
    assert serializer.is_valid()
    updated_option = serializer.save()
    
    assert updated_option.purchase_price == Decimal('22.00')
    assert updated_option.brand == original_brand  # No debe cambiar


@pytest.mark.django_db
def test_is_currently_valid_method(product, supplier):
    """
    Test para el método is_currently_valid en el serializer.
    """
    # Opción válida
    valid_option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Valid Brand',
        purchase_price=Decimal('15.00'),
        valid_from=date.today(),
        valid_to=date.today() + timedelta(days=30)
    )
    
    # Opción expirada
    expired_option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Expired Brand',
        purchase_price=Decimal('12.00'),
        valid_from=date.today() - timedelta(days=60),
        valid_to=date.today() - timedelta(days=10)
    )
    
    valid_serializer = PurchaseOptionSerializer(valid_option)
    expired_serializer = PurchaseOptionSerializer(expired_option)
    
    assert valid_serializer.data['is_currently_valid'] is True
    assert expired_serializer.data['is_currently_valid'] is False


@pytest.mark.django_db
def test_serialize_detailed_purchase_option(purchase_option):
    """
    Test para el serializer detallado de opción de compra.
    """
    factory = APIRequestFactory()
    request = factory.get('/')
    
    serializer = PurchaseOptionDetailSerializer(
        purchase_option, 
        context={'request': Request(request)}
    )
    data = serializer.data
    
    # Debe incluir objetos completos del producto y proveedor
    assert isinstance(data['product'], dict)
    assert isinstance(data['supplier'], dict)
    assert 'name' in data['product']
    assert 'name' in data['supplier']
    assert data['product']['name'] == purchase_option.product.name
    assert data['supplier']['name'] == purchase_option.supplier.name


@pytest.mark.django_db
def test_nested_objects_are_read_only(purchase_option, product, supplier):
    """
    Test para verificar que los objetos anidados son read-only.
    """
    # Crear otro producto y proveedor
    another_category = Category.objects.create(name='Another Category')
    another_product = Product.objects.create(
        sku='TST-ANO-PRO-001',
        name='Another Product',
        unit='caja',
        category=another_category
    )
    
    another_supplier = Supplier.objects.create(name='Another Supplier')
    
    data = {
        'product': {
            'id': another_product.id,
            'name': 'Attempt to change product'
        },
        'supplier': {
            'id': another_supplier.id,
            'name': 'Attempt to change supplier'
        },
        'brand': 'Updated Brand',
        'purchase_price': '25.00'
    }
    
    serializer = PurchaseOptionDetailSerializer(purchase_option, data=data, partial=True)
    
    # El serializer debe seguir siendo válido pero ignorar los cambios en objetos anidados
    if serializer.is_valid():
        updated_option = serializer.save()
        
        # Los objetos relacionados no deben cambiar
        assert updated_option.product == purchase_option.product
        assert updated_option.supplier == purchase_option.supplier
        # Solo el brand debe cambiar
        assert updated_option.brand == 'Updated Brand' 
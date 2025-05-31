import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta
from decimal import Decimal

from suppliers.models import Supplier, PurchaseOption
from catalogs.models import Category, Product

User = get_user_model()


@pytest.fixture
def authenticated_api_client():
    """
    Fixture que proporciona un cliente API autenticado.
    """
    client = APIClient()
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def sample_data():
    """
    Fixture que proporciona datos de muestra para los tests.
    """
    # Crear categoría
    category = Category.objects.create(
        name='Instrumental Dental',
        description='Herramientas dentales'
    )
    
    # Crear productos
    product1 = Product.objects.create(
        sku='INS-DEN-JER-001',
        name='Jeringa Dental',
        description='Jeringa para procedimientos dentales',
        unit='unidad',
        category=category
    )
    
    product2 = Product.objects.create(
        sku='INS-DEN-ESP-001',
        name='Espejo Dental',
        description='Espejo para examinación dental',
        unit='unidad',
        category=category
    )
    
    # Crear proveedores
    supplier1 = Supplier.objects.create(
        name='Dental Supplies Inc.',
        contact_name='Juan Pérez',
        phone='+1-555-0123',
        email='contacto@dentalsupplies.com'
    )
    
    supplier2 = Supplier.objects.create(
        name='Medical Tools Ltd.',
        contact_name='María García',
        phone='+1-555-0456',
        email='info@medicaltools.com'
    )
    
    return {
        'category': category,
        'products': [product1, product2],
        'suppliers': [supplier1, supplier2]
    }


@pytest.fixture
def supplier():
    """
    Fixture que crea un proveedor de muestra.
    """
    return Supplier.objects.create(
        name='Test Supplier',
        contact_name='Test Contact',
        phone='+1-555-0123',
        email='test@supplier.com'
    )


@pytest.fixture
def supplier_data():
    """
    Fixture con datos para crear proveedores.
    """
    return {
        'name': 'Test Supplier',
        'contact_name': 'Test Contact',
        'phone': '+1-555-0123',
        'email': 'test@supplier.com'
    }


@pytest.fixture
def purchase_option_setup():
    """
    Fixture que crea los datos necesarios para tests de PurchaseOption.
    """
    # Crear datos de muestra
    category = Category.objects.create(
        name='Test Category',
        description='Test description'
    )
    
    product = Product.objects.create(
        sku='TST-PRO-001',
        name='Test Product',
        description='Test product description',
        unit='unidad',
        category=category
    )
    
    supplier = Supplier.objects.create(
        name='Test Supplier',
        contact_name='Test Contact',
        email='test@supplier.com'
    )
    
    purchase_option_data = {
        'product': product.id,
        'supplier': supplier.id,
        'brand': 'Test Brand',
        'purchase_price': '15.50',
        'valid_from': date.today().isoformat(),
        'valid_to': (date.today() + timedelta(days=90)).isoformat()
    }
    
    purchase_option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Existing Brand',
        purchase_price=Decimal('12.00'),
        valid_from=date.today()
    )
    
    return {
        'category': category,
        'product': product,
        'supplier': supplier,
        'purchase_option_data': purchase_option_data,
        'purchase_option': purchase_option
    }


# Tests para la API de Supplier

@pytest.mark.django_db
def test_supplier_authentication_required():
    """
    Test para verificar que se requiere autenticación.
    """
    client = APIClient()  # Cliente sin autenticar
    url = reverse('supplier-list')
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_list_suppliers(authenticated_api_client, supplier):
    """
    Test para listar proveedores.
    """
    url = reverse('supplier-list')
    response = authenticated_api_client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['name'] == supplier.name


@pytest.mark.django_db
def test_create_supplier(authenticated_api_client):
    """
    Test para crear un nuevo proveedor.
    """
    url = reverse('supplier-list')
    new_supplier_data = {
        'name': 'New Supplier',
        'contact_name': 'New Contact',
        'phone': '+1-555-9999',
        'email': 'new@supplier.com'
    }
    
    response = authenticated_api_client.post(url, new_supplier_data, format='json')
    
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['name'] == new_supplier_data['name']
    assert Supplier.objects.filter(name='New Supplier').exists()


@pytest.mark.django_db
def test_create_supplier_minimal_data(authenticated_api_client):
    """
    Test para crear un proveedor con datos mínimos.
    """
    url = reverse('supplier-list')
    minimal_data = {'name': 'Minimal Supplier'}
    
    response = authenticated_api_client.post(url, minimal_data, format='json')
    
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['name'] == 'Minimal Supplier'


@pytest.mark.django_db
def test_create_supplier_invalid_data(authenticated_api_client):
    """
    Test para crear un proveedor con datos inválidos.
    """
    url = reverse('supplier-list')
    invalid_data = {
        'name': '',  # Campo requerido vacío
        'email': 'invalid-email'  # Email inválido
    }
    
    response = authenticated_api_client.post(url, invalid_data, format='json')
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'name' in response.data


@pytest.mark.django_db
def test_retrieve_supplier(authenticated_api_client, supplier):
    """
    Test para obtener un proveedor específico.
    """
    url = reverse('supplier-detail', kwargs={'pk': supplier.pk})
    response = authenticated_api_client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data['name'] == supplier.name
    assert response.data['id'] == supplier.id


@pytest.mark.django_db
def test_update_supplier(authenticated_api_client, supplier):
    """
    Test para actualizar un proveedor.
    """
    url = reverse('supplier-detail', kwargs={'pk': supplier.pk})
    updated_data = {
        'name': 'Updated Supplier',
        'contact_name': 'Updated Contact',
        'phone': '+1-555-8888',
        'email': 'updated@supplier.com'
    }
    
    response = authenticated_api_client.put(url, updated_data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data['name'] == 'Updated Supplier'
    
    # Verificar en la base de datos
    supplier.refresh_from_db()
    assert supplier.name == 'Updated Supplier'


@pytest.mark.django_db
def test_partial_update_supplier(authenticated_api_client, supplier, supplier_data):
    """
    Test para actualizar parcialmente un proveedor.
    """
    url = reverse('supplier-detail', kwargs={'pk': supplier.pk})
    partial_data = {'name': 'Partially Updated'}
    
    response = authenticated_api_client.patch(url, partial_data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data['name'] == 'Partially Updated'
    
    # Verificar que otros campos no cambiaron
    supplier.refresh_from_db()
    assert supplier.name == 'Partially Updated'
    assert supplier.contact_name == supplier_data['contact_name']


@pytest.mark.django_db
def test_delete_supplier(authenticated_api_client, supplier):
    """
    Test para eliminar un proveedor.
    """
    url = reverse('supplier-detail', kwargs={'pk': supplier.pk})
    response = authenticated_api_client.delete(url)
    
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Supplier.objects.filter(pk=supplier.pk).exists()


@pytest.mark.django_db
def test_filter_suppliers_by_name(authenticated_api_client, supplier):
    """
    Test para filtrar proveedores por nombre.
    """
    # Crear otro proveedor
    Supplier.objects.create(name='Another Supplier')
    
    url = reverse('supplier-list')
    response = authenticated_api_client.get(url, {'name': 'Test'})
    
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['name'] == supplier.name


@pytest.mark.django_db
def test_search_suppliers(authenticated_api_client, supplier):
    """
    Test para buscar proveedores.
    """
    url = reverse('supplier-list')
    response = authenticated_api_client.get(url, {'search': 'Test'})
    
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['name'] == supplier.name


@pytest.mark.django_db
def test_ordering_suppliers(authenticated_api_client, supplier):
    """
    Test para ordenar proveedores.
    """
    Supplier.objects.create(name='Alpha Supplier')
    Supplier.objects.create(name='Zeta Supplier')
    
    url = reverse('supplier-list')
    response = authenticated_api_client.get(url, {'ordering': 'name'})
    
    assert response.status_code == status.HTTP_200_OK
    names = [item['name'] for item in response.data['results']]
    assert names == sorted(names)


@pytest.mark.django_db
def test_supplier_purchase_options_action(authenticated_api_client, supplier):
    """
    Test para la acción personalizada purchase_options.
    """
    # Crear datos para purchase option
    category = Category.objects.create(name='Test Category')
    product = Product.objects.create(
        sku='TST-ACT-001',
        name='Test Product',
        unit='unidad',
        category=category
    )
    
    PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Test Brand',
        purchase_price=Decimal('8.00'),
        valid_from=date.today()
    )
    
    url = reverse('supplier-purchase-options', kwargs={'pk': supplier.pk})
    response = authenticated_api_client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]['brand'] == 'Test Brand'


# Tests para la API de PurchaseOption

@pytest.mark.django_db
def test_purchase_option_authentication_required():
    """
    Test para verificar que se requiere autenticación.
    """
    client = APIClient()  # Cliente sin autenticar
    url = reverse('purchaseoption-list')
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_list_purchase_options(authenticated_api_client, purchase_option_setup):
    """
    Test para listar opciones de compra.
    """
    url = reverse('purchaseoption-list')
    response = authenticated_api_client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['brand'] == 'Existing Brand'


@pytest.mark.django_db
def test_create_purchase_option(authenticated_api_client, purchase_option_setup):
    """
    Test para crear una nueva opción de compra.
    """
    url = reverse('purchaseoption-list')
    
    response = authenticated_api_client.post(
        url, 
        purchase_option_setup['purchase_option_data'], 
        format='json'
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['brand'] == 'Test Brand'
    assert response.data['purchase_price'] == '15.50'
    assert PurchaseOption.objects.filter(brand='Test Brand').exists()


@pytest.mark.django_db
def test_create_purchase_option_without_valid_to(authenticated_api_client, purchase_option_setup):
    """
    Test para crear una opción de compra sin fecha de vencimiento.
    """
    url = reverse('purchaseoption-list')
    data = purchase_option_setup['purchase_option_data'].copy()
    del data['valid_to']
    data['brand'] = 'No Expiry Brand'
    
    response = authenticated_api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['valid_to'] is None


@pytest.mark.django_db
def test_create_purchase_option_invalid_data(authenticated_api_client, purchase_option_setup):
    """
    Test para crear una opción de compra con datos inválidos.
    """
    url = reverse('purchaseoption-list')
    invalid_data = {
        'product': 999,  # ID inexistente
        'supplier': purchase_option_setup['supplier'].id,
        'brand': 'Test Brand',
        'purchase_price': 'invalid_price'
    }
    
    response = authenticated_api_client.post(url, invalid_data, format='json')
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_retrieve_purchase_option(authenticated_api_client, purchase_option_setup):
    """
    Test para obtener una opción de compra específica.
    """
    purchase_option = purchase_option_setup['purchase_option']
    url = reverse('purchaseoption-detail', kwargs={'pk': purchase_option.pk})
    response = authenticated_api_client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data['brand'] == 'Existing Brand'
    assert response.data['id'] == purchase_option.id


@pytest.mark.django_db
def test_update_purchase_option(authenticated_api_client, purchase_option_setup):
    """
    Test para actualizar una opción de compra.
    """
    purchase_option = purchase_option_setup['purchase_option']
    product = purchase_option_setup['product']
    supplier = purchase_option_setup['supplier']
    
    url = reverse('purchaseoption-detail', kwargs={'pk': purchase_option.pk})
    updated_data = {
        'product': product.id,
        'supplier': supplier.id,
        'brand': 'Updated Brand',
        'purchase_price': '18.00',
        'valid_from': date.today().isoformat()
    }
    
    response = authenticated_api_client.put(url, updated_data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data['brand'] == 'Updated Brand'
    assert response.data['purchase_price'] == '18.00'


@pytest.mark.django_db
def test_partial_update_purchase_option(authenticated_api_client, purchase_option_setup):
    """
    Test para actualizar parcialmente una opción de compra.
    """
    purchase_option = purchase_option_setup['purchase_option']
    url = reverse('purchaseoption-detail', kwargs={'pk': purchase_option.pk})
    partial_data = {'purchase_price': '20.00'}
    
    response = authenticated_api_client.patch(url, partial_data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data['purchase_price'] == '20.00'
    assert response.data['brand'] == 'Existing Brand'  # No cambió


@pytest.mark.django_db
def test_delete_purchase_option(authenticated_api_client, purchase_option_setup):
    """
    Test para eliminar una opción de compra.
    """
    purchase_option = purchase_option_setup['purchase_option']
    url = reverse('purchaseoption-detail', kwargs={'pk': purchase_option.pk})
    response = authenticated_api_client.delete(url)
    
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not PurchaseOption.objects.filter(pk=purchase_option.pk).exists()


@pytest.mark.django_db
def test_filter_by_product(authenticated_api_client, purchase_option_setup):
    """
    Test para filtrar opciones de compra por producto.
    """
    product = purchase_option_setup['product']
    url = reverse('purchaseoption-list')
    response = authenticated_api_client.get(url, {'product': product.id})
    
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['product'] == product.id


@pytest.mark.django_db
def test_filter_by_supplier(authenticated_api_client, purchase_option_setup):
    """
    Test para filtrar opciones de compra por proveedor.
    """
    supplier = purchase_option_setup['supplier']
    url = reverse('purchaseoption-list')
    response = authenticated_api_client.get(url, {'supplier': supplier.id})
    
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['supplier'] == supplier.id


@pytest.mark.django_db
def test_filter_by_price_range(authenticated_api_client, purchase_option_setup):
    """
    Test para filtrar opciones de compra por rango de precio.
    """
    url = reverse('purchaseoption-list')
    response = authenticated_api_client.get(url, {'min_price': 10, 'max_price': 15})
    
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 1
    assert float(response.data['results'][0]['purchase_price']) == 12.00


@pytest.mark.django_db
def test_filter_currently_valid(authenticated_api_client, purchase_option_setup):
    """
    Test para filtrar opciones de compra actualmente válidas.
    """
    product = purchase_option_setup['product']
    supplier = purchase_option_setup['supplier']
    
    # Crear opción expirada
    PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Expired Brand',
        purchase_price=Decimal('10.00'),
        valid_from=date.today() - timedelta(days=100),
        valid_to=date.today() - timedelta(days=10)
    )
    
    url = reverse('purchaseoption-list')
    response = authenticated_api_client.get(url, {'is_currently_valid': 'true'})
    
    assert response.status_code == status.HTTP_200_OK
    # Solo debe aparecer la opción válida
    brands = [item['brand'] for item in response.data['results']]
    assert 'Existing Brand' in brands
    assert 'Expired Brand' not in brands


@pytest.mark.django_db
def test_search_purchase_options(authenticated_api_client, purchase_option_setup):
    """
    Test para buscar opciones de compra.
    """
    url = reverse('purchaseoption-list')
    response = authenticated_api_client.get(url, {'search': 'Existing'})
    
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['brand'] == 'Existing Brand'


@pytest.mark.django_db
def test_ordering_purchase_options(authenticated_api_client, purchase_option_setup):
    """
    Test para ordenar opciones de compra.
    """
    product = purchase_option_setup['product']
    supplier = purchase_option_setup['supplier']
    
    # Crear otra opción con precio diferente
    PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Higher Price Brand',
        purchase_price=Decimal('25.00'),
        valid_from=date.today()
    )
    
    url = reverse('purchaseoption-list')
    response = authenticated_api_client.get(url, {'ordering': 'purchase_price'})
    
    assert response.status_code == status.HTTP_200_OK
    prices = [float(item['purchase_price']) for item in response.data['results']]
    assert prices == sorted(prices)


@pytest.mark.django_db
def test_valid_options_action(authenticated_api_client, purchase_option_setup):
    """
    Test para la acción personalizada valid_options.
    """
    product = purchase_option_setup['product']
    supplier = purchase_option_setup['supplier']
    
    # Crear opción expirada
    PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Expired Brand',
        purchase_price=Decimal('10.00'),
        valid_from=date.today() - timedelta(days=100),
        valid_to=date.today() - timedelta(days=10)
    )
    
    # Crear opción futura
    PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Future Brand',
        purchase_price=Decimal('15.00'),
        valid_from=date.today() + timedelta(days=10)
    )
    
    url = reverse('purchaseoption-valid-options')
    response = authenticated_api_client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    # Solo debe aparecer la opción válida
    brands = [item['brand'] for item in response.data['results']]
    assert 'Existing Brand' in brands
    assert 'Expired Brand' not in brands
    assert 'Future Brand' not in brands


@pytest.mark.django_db
def test_purchase_option_serializer_fields(authenticated_api_client, purchase_option_setup):
    """
    Test para verificar los campos del serializer.
    """
    purchase_option = purchase_option_setup['purchase_option']
    product = purchase_option_setup['product']
    supplier = purchase_option_setup['supplier']
    category = purchase_option_setup['category']
    
    url = reverse('purchaseoption-detail', kwargs={'pk': purchase_option.pk})
    response = authenticated_api_client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verificar campos calculados
    assert 'product_name' in response.data
    assert 'supplier_name' in response.data
    assert 'category_name' in response.data
    assert 'is_currently_valid' in response.data
    
    # Verificar valores
    assert response.data['product_name'] == product.name
    assert response.data['supplier_name'] == supplier.name
    assert response.data['category_name'] == category.name
    assert response.data['is_currently_valid'] is True


@pytest.mark.django_db
def test_unique_constraint_validation(authenticated_api_client, purchase_option_setup):
    """
    Test para verificar la validación de restricción única.
    """
    purchase_option = purchase_option_setup['purchase_option']
    product = purchase_option_setup['product']
    supplier = purchase_option_setup['supplier']
    
    url = reverse('purchaseoption-list')
    
    # Intentar crear opción duplicada
    duplicate_data = {
        'product': product.id,
        'supplier': supplier.id,
        'brand': 'Existing Brand',
        'purchase_price': '15.00',
        'valid_from': purchase_option.valid_from.isoformat()
    }
    
    response = authenticated_api_client.post(url, duplicate_data, format='json')
    
    # Debe fallar por violación de restricción única
    assert response.status_code == status.HTTP_400_BAD_REQUEST 
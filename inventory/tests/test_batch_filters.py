import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from inventory.models import Location, InventoryStock
from catalogs.models import Category, Product, ProductBatch

User = get_user_model()


@pytest.fixture
def api_client_authenticated():
    """Fixture para un cliente API autenticado."""
    client = APIClient()
    user_data = {
        'username': 'testuser_batch_filters',
        'password': 'Str0ngP@sswOrd!BATCH',
        'email': 'testuser_batch@example.com'
    }
    # Limpiar usuario si existe de una ejecución anterior
    User.objects.filter(username=user_data['username']).delete()
    
    # Registrar usuario
    try:
        register_url = reverse('user-list')
    except:
        register_url = "/api/auth/users/"
    client.post(register_url, user_data, format='json')

    # Loguear usuario
    try:
        login_url = reverse('login')
    except:
        login_url = "/api/auth/token/login/"
    login_payload = {'username': user_data['username'], 'password': user_data['password']}
    response = client.post(login_url, login_payload, format='json')
    token = response.data['auth_token']
    client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    return client


@pytest.fixture
def test_batch_data():
    """Fixture para crear datos de prueba con lotes."""
    # Crear categoría y productos
    category = Category.objects.create(
        name='Test Category Batch', 
        description='For batch filter tests'
    )
    
    # Producto que requiere control de lotes
    product_with_batch = Product.objects.create(
        sku='BATCH-TEST-001',
        name='Test Product With Batch',
        description='Product with batch control',
        unit='unidad',
        category=category,
        requires_batch_control=True
    )
    
    # Producto sin control de lotes
    product_without_batch = Product.objects.create(
        sku='NOBATCH-TEST-001',
        name='Test Product Without Batch',
        description='Product without batch control',
        unit='unidad',
        category=category,
        requires_batch_control=False
    )
    
    # Crear ubicaciones
    sede_norte = Location.objects.create(
        name='Sede Norte',
        type='sede',
        address='Calle Norte 123'
    )
    
    sede_sur = Location.objects.create(
        name='Sede Sur',
        type='sede',
        address='Calle Sur 456'
    )
    
    bodega = Location.objects.create(
        name='Bodega Central',
        type='bodega',
        address='Zona Industrial'
    )
    
    # Crear lotes
    batch1 = ProductBatch.objects.create(
        product=product_with_batch,
        batch_number='LOT-001',
        manufacturing_date=date.today() - timedelta(days=30),
        expiry_date=date.today() + timedelta(days=30),
        supplier_reference='SUP-REF-001',
        notes='Lote de prueba 1'
    )
    
    batch2 = ProductBatch.objects.create(
        product=product_with_batch,
        batch_number='LOT-002',
        manufacturing_date=date.today() - timedelta(days=15),
        expiry_date=date.today() + timedelta(days=60),
        supplier_reference='SUP-REF-002',
        notes='Lote de prueba 2'
    )
    
    batch3_expired = ProductBatch.objects.create(
        product=product_with_batch,
        batch_number='LOT-EXPIRED',
        manufacturing_date=date.today() - timedelta(days=90),
        expiry_date=date.today() - timedelta(days=5),
        supplier_reference='SUP-REF-EXPIRED',
        notes='Lote vencido'
    )
    
    # Crear stock de inventario
    # Lote 1 en diferentes ubicaciones
    InventoryStock.objects.create(
        product=product_with_batch,
        location=sede_norte,
        batch=batch1,
        quantity=50
    )
    
    InventoryStock.objects.create(
        product=product_with_batch,
        location=sede_sur,
        batch=batch1,
        quantity=25
    )
    
    InventoryStock.objects.create(
        product=product_with_batch,
        location=bodega,
        batch=batch1,
        quantity=100
    )
    
    # Lote 2 solo en sede norte
    InventoryStock.objects.create(
        product=product_with_batch,
        location=sede_norte,
        batch=batch2,
        quantity=75
    )
    
    # Lote vencido en bodega
    InventoryStock.objects.create(
        product=product_with_batch,
        location=bodega,
        batch=batch3_expired,
        quantity=10
    )
    
    # Producto sin lote
    InventoryStock.objects.create(
        product=product_without_batch,
        location=sede_norte,
        quantity=200
    )
    
    return {
        'category': category,
        'product_with_batch': product_with_batch,
        'product_without_batch': product_without_batch,
        'sede_norte': sede_norte,
        'sede_sur': sede_sur,
        'bodega': bodega,
        'batch1': batch1,
        'batch2': batch2,
        'batch3_expired': batch3_expired
    }


@pytest.mark.django_db
class TestBatchFilters:
    """Tests para los nuevos filtros de lotes."""

    def setup_method(self):
        self.stock_url = reverse('inventorystock-list')

    def test_filter_by_batch_id(self, api_client_authenticated, test_batch_data):
        """Prueba filtrar por ID del lote específico."""
        batch1 = test_batch_data['batch1']
        
        response = api_client_authenticated.get(self.stock_url, {'batch': batch1.id})
        assert response.status_code == 200
        
        results = response.data['results']
        assert len(results) == 3  # Batch1 está en 3 ubicaciones
        
        for result in results:
            assert result['batch_details']['id'] == batch1.id
            assert result['batch_number'] == 'LOT-001'

    def test_filter_by_batch_number(self, api_client_authenticated, test_batch_data):
        """Prueba filtrar por número de lote exacto."""
        response = api_client_authenticated.get(self.stock_url, {'batch_number': 'LOT-002'})
        assert response.status_code == 200
        
        results = response.data['results']
        assert len(results) == 1  # LOT-002 está solo en sede norte
        assert results[0]['batch_number'] == 'LOT-002'
        assert results[0]['location_name'] == 'Sede Norte'

    def test_filter_by_batch_number_contains(self, api_client_authenticated, test_batch_data):
        """Prueba filtrar por texto contenido en número de lote."""
        response = api_client_authenticated.get(self.stock_url, {'batch_number_contains': 'LOT'})
        assert response.status_code == 200
        
        results = response.data['results']
        assert len(results) >= 5  # Todos los lotes contienen 'LOT'

    def test_filter_requires_batch_control(self, api_client_authenticated, test_batch_data):
        """Prueba filtrar productos que requieren control de lotes."""
        response = api_client_authenticated.get(self.stock_url, {'requires_batch_control': 'true'})
        assert response.status_code == 200
        
        results = response.data['results']
        for result in results:
            assert result['product_name'] == 'Test Product With Batch'

    def test_filter_has_batch(self, api_client_authenticated, test_batch_data):
        """Prueba filtrar por existencia de lote."""
        # Con lote
        response = api_client_authenticated.get(self.stock_url, {'has_batch': 'true'})
        assert response.status_code == 200
        
        results = response.data['results']
        for result in results:
            assert result['batch'] is not None
        
        # Sin lote
        response = api_client_authenticated.get(self.stock_url, {'has_batch': 'false'})
        assert response.status_code == 200
        
        results = response.data['results']
        for result in results:
            assert result['batch'] is None

    def test_filter_by_expiry_date_range(self, api_client_authenticated, test_batch_data):
        """Prueba filtrar por rango de fechas de vencimiento."""
        today = date.today()
        future_date = today + timedelta(days=45)
        
        response = api_client_authenticated.get(self.stock_url, {
            'expiry_from': today.isoformat(),
            'expiry_to': future_date.isoformat()
        })
        assert response.status_code == 200
        
        results = response.data['results']
        # Debe incluir LOT-001 (vence en 30 días) pero no LOT-002 (vence en 60 días)
        batch_numbers = [r['batch_number'] for r in results if r['batch_number']]
        assert 'LOT-001' in batch_numbers
        assert 'LOT-002' not in batch_numbers

    def test_filter_expiry_days_ahead(self, api_client_authenticated, test_batch_data):
        """Prueba filtrar productos que vencen en los próximos N días."""
        response = api_client_authenticated.get(self.stock_url, {'expiry_days_ahead': '45'})
        assert response.status_code == 200
        
        results = response.data['results']
        # Debe incluir LOT-001 (vence en 30 días)
        batch_numbers = [r['batch_number'] for r in results if r['batch_number']]
        assert 'LOT-001' in batch_numbers

    def test_filter_is_expired(self, api_client_authenticated, test_batch_data):
        """Prueba filtrar lotes vencidos."""
        response = api_client_authenticated.get(self.stock_url, {'is_expired': 'true'})
        assert response.status_code == 200
        
        results = response.data['results']
        assert len(results) == 1  # Solo el lote vencido
        assert results[0]['batch_number'] == 'LOT-EXPIRED'
        assert results[0]['is_expired'] is True


@pytest.mark.django_db
class TestBatchStockEndpoints:
    """Tests para los nuevos endpoints de stock por lotes."""

    def test_batch_stock_by_locations(self, api_client_authenticated, test_batch_data):
        """Prueba obtener stock de un lote específico por ubicaciones."""
        product = test_batch_data['product_with_batch']
        batch1 = test_batch_data['batch1']
        
        url = reverse('inventorystock-batch-stock-by-locations')
        response = api_client_authenticated.get(url, {
            'product': product.id,
            'batch': batch1.id
        })
        
        assert response.status_code == 200
        data = response.data
        
        assert data['product_id'] == product.id
        assert data['batch_id'] == batch1.id
        assert data['batch_number'] == 'LOT-001'
        assert len(data['locations']) == 3  # 3 ubicaciones
        assert data['total_quantity'] == 175  # 50 + 25 + 100

    def test_product_batches_stock(self, api_client_authenticated, test_batch_data):
        """Prueba obtener todos los lotes de un producto con stock."""
        product = test_batch_data['product_with_batch']
        
        url = reverse('inventorystock-product-batches-stock')
        response = api_client_authenticated.get(url, {'product': product.id})
        
        assert response.status_code == 200
        data = response.data
        
        assert data['product_id'] == product.id
        assert len(data['batches']) == 2  # No incluye el vencido por defecto
        assert data['total_stock'] == 250  # 175 (LOT-001) + 75 (LOT-002)

    def test_product_batches_stock_include_expired(self, api_client_authenticated, test_batch_data):
        """Prueba obtener lotes incluyendo vencidos."""
        product = test_batch_data['product_with_batch']
        
        url = reverse('inventorystock-product-batches-stock')
        response = api_client_authenticated.get(url, {
            'product': product.id,
            'include_expired': 'true'
        })
        
        assert response.status_code == 200
        data = response.data
        
        assert len(data['batches']) == 3  # Incluye el vencido
        assert data['total_stock'] == 260  # Incluye los 10 del lote vencido

    def test_location_batch_stock(self, api_client_authenticated, test_batch_data):
        """Prueba obtener stock de lotes en una ubicación específica."""
        sede_norte = test_batch_data['sede_norte']
        
        url = reverse('inventorystock-location-batch-stock')
        response = api_client_authenticated.get(url, {'location': sede_norte.id})
        
        assert response.status_code == 200
        data = response.data
        
        assert data['location_id'] == sede_norte.id
        assert data['location_name'] == 'Sede Norte'
        assert len(data['products']) == 1  # Solo products with batch control
        
        product_data = data['products'][0]
        assert len(product_data['batches']) == 2  # LOT-001 y LOT-002 en sede norte
        assert product_data['total_quantity'] == 125  # 50 + 75

    def test_endpoint_error_handling(self, api_client_authenticated, test_batch_data):
        """Prueba manejo de errores en los endpoints."""
        # Sin parámetros requeridos
        url = reverse('inventorystock-batch-stock-by-locations')
        response = api_client_authenticated.get(url)
        assert response.status_code == 400
        
        # Producto inexistente
        response = api_client_authenticated.get(url, {
            'product': 99999,
            'batch': 99999
        })
        assert response.status_code == 404 
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from inventory.models import Location, InventoryStock, InventoryMovement
from catalogs.models import Category, Product

User = get_user_model()

@pytest.fixture
def api_client_authenticated():
    """Fixture para un cliente API autenticado."""
    client = APIClient()
    user_data = {
        'username': 'testauthuser_inventory',
        'password': 'Str0ngP@sswOrd!INV',
        'email': 'testauthuser_inventory@example.com'
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
def test_data():
    """Fixture para crear datos de prueba."""
    # Crear categoría y producto de prueba
    category = Category.objects.create(name='Test Category Inventory', description='For inventory tests')
    product = Product.objects.create(
        sku='INV-TEST-001',
        name='Test Product Inventory',
        description='Product for inventory testing',
        unit='unidad',
        category=category
    )
    
    # Crear ubicaciones de prueba
    sede = Location.objects.create(name='Sede Principal', type='sede', address='Calle 123')
    bodega = Location.objects.create(name='Bodega Central', type='bodega', address='Carrera 456')
    
    return {
        'category': category,
        'product': product,
        'sede': sede,
        'bodega': bodega
    }

@pytest.mark.django_db
class TestLocationAPI:
    def setup_method(self):
        self.locations_url = reverse('location-list')

    def test_create_location_sede(self, api_client_authenticated):
        """Prueba crear una ubicación tipo sede."""
        payload = {
            'name': 'Sede Norte',
            'type': 'sede',
            'address': 'Av. Norte 789'
        }
        response = api_client_authenticated.post(self.locations_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        assert Location.objects.filter(name='Sede Norte').exists()
        assert response.data['type'] == 'sede'

    def test_create_location_bodega(self, api_client_authenticated):
        """Prueba crear una ubicación tipo bodega."""
        payload = {
            'name': 'Bodega Sur',
            'type': 'bodega',
            'address': 'Zona Industrial Sur'
        }
        response = api_client_authenticated.post(self.locations_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        assert response.data['type'] == 'bodega'

    def test_create_location_invalid_type(self, api_client_authenticated):
        """Prueba crear una ubicación con tipo inválido."""
        payload = {
            'name': 'Ubicación Inválida',
            'type': 'oficina',  # Tipo no permitido
            'address': 'Dirección test'
        }
        response = api_client_authenticated.post(self.locations_url, payload, format='json')
        assert response.status_code == 400

    def test_create_location_unauthenticated(self):
        """Prueba que un usuario no autenticado no puede crear ubicaciones."""
        client = APIClient()
        payload = {'name': 'Test Unauth', 'type': 'sede'}
        response = client.post(self.locations_url, payload, format='json')
        assert response.status_code == 401

    def test_list_locations(self, api_client_authenticated, test_data):
        """Prueba obtener lista de ubicaciones."""
        response = api_client_authenticated.get(self.locations_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert len(response.data['results']) >= 2

    def test_filter_locations_by_type(self, api_client_authenticated, test_data):
        """Prueba filtrar ubicaciones por tipo."""
        response = api_client_authenticated.get(self.locations_url, {'type': 'sede'})
        assert response.status_code == 200
        for location in response.data['results']:
            assert location['type'] == 'sede'

    def test_search_locations(self, api_client_authenticated, test_data):
        """Prueba búsqueda de ubicaciones."""
        response = api_client_authenticated.get(self.locations_url, {'search': 'Principal'})
        assert response.status_code == 200
        found = any('Principal' in loc['name'] for loc in response.data['results'])
        assert found

    def test_retrieve_location(self, api_client_authenticated, test_data):
        """Prueba obtener detalle de una ubicación."""
        detail_url = reverse('location-detail', kwargs={'pk': test_data['sede'].id})
        response = api_client_authenticated.get(detail_url)
        assert response.status_code == 200
        assert response.data['name'] == test_data['sede'].name

    def test_update_location(self, api_client_authenticated, test_data):
        """Prueba actualizar una ubicación."""
        location_id = test_data['sede'].id
        detail_url = reverse('location-detail', kwargs={'pk': location_id})
        payload = {
            'name': 'Sede Principal Actualizada',
            'type': 'sede',
            'address': 'Nueva Dirección 999'
        }
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        test_data['sede'].refresh_from_db()
        assert test_data['sede'].name == 'Sede Principal Actualizada'

    def test_partial_update_location(self, api_client_authenticated, test_data):
        """Prueba actualización parcial de una ubicación."""
        location_id = test_data['sede'].id
        detail_url = reverse('location-detail', kwargs={'pk': location_id})
        payload = {'name': 'Sede Parcialmente Actualizada'}
        response = api_client_authenticated.patch(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        test_data['sede'].refresh_from_db()
        assert test_data['sede'].name == 'Sede Parcialmente Actualizada'

    def test_delete_location(self, api_client_authenticated, test_data):
        """Prueba eliminar una ubicación."""
        location = Location.objects.create(name='Temporal', type='bodega')
        detail_url = reverse('location-detail', kwargs={'pk': location.id})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 204
        assert not Location.objects.filter(pk=location.id).exists()

    def test_location_pagination(self, api_client_authenticated):
        """Prueba la paginación para la lista de ubicaciones."""
        # Crear 30 ubicaciones para asegurar que la paginación funcione (PAGE_SIZE es 25)
        for i in range(30):
            Location.objects.create(name=f'Ubicacion Paginada {i}-TEST', type='bodega', address=f'Dir {i}')
        
        response = api_client_authenticated.get(self.locations_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert 'results' in response.data
        
        # Con PAGE_SIZE=25, debe devolver 25 items en la primera página
        assert len(response.data['results']) == 25
        assert response.data['count'] >= 30
        assert response.data['next'] is not None
        assert response.data['previous'] is None

@pytest.mark.django_db
class TestInventoryStockAPI:
    def setup_method(self):
        self.stock_url = reverse('inventorystock-list')

    def test_create_initial_stock(self, api_client_authenticated, test_data):
        """Prueba crear stock inicial."""
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'quantity': 100
        }
        response = api_client_authenticated.post(self.stock_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        assert InventoryStock.objects.filter(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=100
        ).exists()

    def test_create_stock_unauthenticated(self, test_data):
        """Prueba que un usuario no autenticado no puede crear stock."""
        client = APIClient()
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'quantity': 50
        }
        response = client.post(self.stock_url, payload, format='json')
        assert response.status_code == 401

    def test_create_stock_duplicate_product_location(self, api_client_authenticated, test_data):
        """Prueba que no se puede crear stock duplicado para el mismo producto y ubicación."""
        # Crear primer stock
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'quantity': 50
        }
        response1 = api_client_authenticated.post(self.stock_url, payload, format='json')
        assert response1.status_code == 201

        # Intentar crear duplicado
        payload['quantity'] = 75
        response2 = api_client_authenticated.post(self.stock_url, payload, format='json')
        assert response2.status_code == 400

    def test_list_stock(self, api_client_authenticated, test_data):
        """Prueba obtener lista de stock."""
        # Crear stock de prueba
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=50
        )
        
        response = api_client_authenticated.get(self.stock_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert len(response.data['results']) >= 1

    def test_filter_stock_by_location(self, api_client_authenticated, test_data):
        """Prueba filtrar stock por ubicación."""
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=30
        )
        
        response = api_client_authenticated.get(
            self.stock_url, 
            {'location': test_data['sede'].id}
        )
        assert response.status_code == 200
        for stock in response.data['results']:
            assert stock['location'] == test_data['sede'].id


    def test_filter_stock_by_min_quantity(self, api_client_authenticated, test_data):
        """Prueba filtrar stock por cantidad mínima."""
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=5
        )
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['bodega'],
            quantity=25
        )
        
        response = api_client_authenticated.get(self.stock_url, {'min_quantity': 10})
        assert response.status_code == 200
        for stock in response.data['results']:
            assert stock['quantity'] >= 10

    def test_search_stock(self, api_client_authenticated, test_data):
        """Prueba búsqueda de stock por producto o ubicación."""
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=15
        )
        
        response = api_client_authenticated.get(self.stock_url, {'search': 'Test Product'})
        assert response.status_code == 200
        found = any('Test Product' in stock['product_name'] for stock in response.data['results'])
        assert found

    def test_stock_summary_endpoint(self, api_client_authenticated, test_data):
        """Prueba el endpoint de resumen de stock."""
        # Crear stock en diferentes ubicaciones
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=20
        )
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['bodega'],
            quantity=30
        )
        
        summary_url = reverse('inventorystock-summary')
        response = api_client_authenticated.get(summary_url)
        assert response.status_code == 200, f"Error: {response.data}"
        
        # Buscar nuestro producto en el resumen
        product_summary = None
        for item in response.data:
            if item['product_id'] == test_data['product'].id:
                product_summary = item
                break
        
        assert product_summary is not None
        assert product_summary['total_quantity'] == 50
        assert len(product_summary['locations']) == 2

    def test_update_stock(self, api_client_authenticated, test_data):
        """Prueba actualizar stock existente."""
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=40
        )
        
        detail_url = reverse('inventorystock-detail', kwargs={'pk': stock.id})
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'quantity': 80
        }
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        stock.refresh_from_db()
        assert stock.quantity == 80

    def test_partial_update_stock(self, api_client_authenticated, test_data):
        """Prueba actualización parcial de stock."""
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=60
        )
        
        detail_url = reverse('inventorystock-detail', kwargs={'pk': stock.id})
        payload = {'quantity': 120}
        response = api_client_authenticated.patch(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        stock.refresh_from_db()
        assert stock.quantity == 120

    def test_delete_stock(self, api_client_authenticated, test_data):
        """Prueba eliminar stock."""
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=10
        )
        
        detail_url = reverse('inventorystock-detail', kwargs={'pk': stock.id})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 204
        assert not InventoryStock.objects.filter(pk=stock.id).exists()

    def test_stock_pagination(self, api_client_authenticated, test_data):
        """Prueba la paginación para la lista de stock."""
        # Crear múltiples productos con stock
        for i in range(30):
            category = Category.objects.create(name=f'Cat Stock Pagination {i}')
            product = Product.objects.create(
                sku=f'STO-PAG-{i:03d}',
                name=f'Product Stock Pagination {i}',
                unit='unidad',
                category=category
            )
            InventoryStock.objects.create(
                product=product,
                location=test_data['sede'],
                quantity=i + 10
            )
        
        response = api_client_authenticated.get(self.stock_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert 'results' in response.data
        
        # Con PAGE_SIZE=25, debe devolver 25 items en la primera página
        assert len(response.data['results']) == 25
        assert response.data['count'] >= 30

@pytest.mark.django_db
class TestInventoryMovementAPI:
    def setup_method(self):
        self.movements_url = reverse('inventorymovement-list')

    def test_create_entry_movement(self, api_client_authenticated, test_data):
        """Prueba crear un movimiento de entrada."""
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'movement_type': 'in',
            'quantity': 50,
            'notes': 'Compra inicial'
        }
        response = api_client_authenticated.post(self.movements_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        
        # Verificar que se creó el movimiento
        movement = InventoryMovement.objects.get(id=response.data['id'])
        assert movement.movement_type == 'in'
        assert movement.quantity == 50
        
        # Verificar que se actualizó el stock automáticamente
        stock = InventoryStock.objects.get(
            product=test_data['product'],
            location=test_data['sede']
        )
        assert stock.quantity == 50

    def test_create_exit_movement(self, api_client_authenticated, test_data):
        """Prueba crear un movimiento de salida."""
        # Primero crear stock inicial
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=100
        )
        
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'movement_type': 'out',
            'quantity': 30,
            'notes': 'Venta a cliente'
        }
        response = api_client_authenticated.post(self.movements_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        
        # Verificar que se actualizó el stock
        stock = InventoryStock.objects.get(
            product=test_data['product'],
            location=test_data['sede']
        )
        assert stock.quantity == 70

    def test_create_movement_with_expiry_date(self, api_client_authenticated, test_data):
        """Prueba crear un movimiento con fecha de vencimiento."""
        expiry_date = date.today() + timedelta(days=365)
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'movement_type': 'in',
            'quantity': 25,
            'expiry_date': expiry_date.isoformat(),
            'notes': 'Lote con vencimiento'
        }
        response = api_client_authenticated.post(self.movements_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        
        movement = InventoryMovement.objects.get(id=response.data['id'])
        assert movement.expiry_date == expiry_date

    def test_create_movement_unauthenticated(self, test_data):
        """Prueba que un usuario no autenticado no puede crear movimientos."""
        client = APIClient()
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'movement_type': 'in',
            'quantity': 20
        }
        response = client.post(self.movements_url, payload, format='json')
        assert response.status_code == 401

    def test_create_movement_invalid_type(self, api_client_authenticated, test_data):
        """Prueba crear movimiento con tipo inválido."""
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'movement_type': 'invalid',  # Tipo no permitido
            'quantity': 10
        }
        response = api_client_authenticated.post(self.movements_url, payload, format='json')
        assert response.status_code == 400

    def test_create_movement_negative_quantity(self, api_client_authenticated, test_data):
        """Prueba crear movimiento con cantidad negativa."""
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'movement_type': 'in',
            'quantity': -10  # Cantidad negativa
        }
        response = api_client_authenticated.post(self.movements_url, payload, format='json')
        assert response.status_code == 400

    def test_list_movements(self, api_client_authenticated, test_data):
        """Prueba obtener lista de movimientos."""
        # Crear algunos movimientos
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=20
        )
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='out',
            quantity=5
        )
        
        response = api_client_authenticated.get(self.movements_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert len(response.data['results']) >= 2

    def test_filter_movements_by_type(self, api_client_authenticated, test_data):
        """Prueba filtrar movimientos por tipo."""
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=15
        )
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='out',
            quantity=8
        )
        
        response = api_client_authenticated.get(
            self.movements_url, 
            {'movement_type': 'in'}
        )
        assert response.status_code == 200
        for movement in response.data['results']:
            assert movement['movement_type'] == 'in'

    def test_filter_movements_by_location(self, api_client_authenticated, test_data):
        """Prueba filtrar movimientos por ubicación."""
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=12
        )
        
        response = api_client_authenticated.get(
            self.movements_url,
            {'location': test_data['sede'].id}
        )
        assert response.status_code == 200
        for movement in response.data['results']:
            assert movement['location'] == test_data['sede'].id

    def test_filter_movements_by_product(self, api_client_authenticated, test_data):
        """Prueba filtrar movimientos por producto."""
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=18
        )
        
        response = api_client_authenticated.get(
            self.movements_url,
            {'product': test_data['product'].id}
        )
        assert response.status_code == 200
        for movement in response.data['results']:
            assert movement['product'] == test_data['product'].id

    def test_filter_movements_by_date_range(self, api_client_authenticated, test_data):
        """Prueba filtrar movimientos por rango de fechas."""
        # Crear movimiento de ayer
        yesterday = timezone.now() - timedelta(days=1)
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=10
        )
        # Cambiar manualmente la fecha
        movement.occurred_at = yesterday
        movement.save()
        
        # Filtrar por fecha de hoy
        today = date.today()
        response = api_client_authenticated.get(
            self.movements_url,
            {
                'date_from': today.isoformat(),
                'date_to': today.isoformat()
            }
        )
        assert response.status_code == 200

    def test_search_movements(self, api_client_authenticated, test_data):
        """Prueba búsqueda de movimientos."""
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=22,
            notes='Compra especial para evento'
        )
        
        response = api_client_authenticated.get(self.movements_url, {'search': 'especial'})
        assert response.status_code == 200
        found = any('especial' in mov.get('notes', '') for mov in response.data['results'])
        assert found

    def test_retrieve_movement(self, api_client_authenticated, test_data):
        """Prueba obtener detalle de un movimiento."""
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=35,
            notes='Movimiento de prueba'
        )
        
        detail_url = reverse('inventorymovement-detail', kwargs={'pk': movement.id})
        response = api_client_authenticated.get(detail_url)
        assert response.status_code == 200
        assert response.data['quantity'] == 35
        assert response.data['notes'] == 'Movimiento de prueba'

    def test_update_movement(self, api_client_authenticated, test_data):
        """Prueba actualizar un movimiento."""
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=40,
            notes='Notas originales'
        )
        
        detail_url = reverse('inventorymovement-detail', kwargs={'pk': movement.id})
        payload = {
            'product': test_data['product'].id,
            'location': test_data['sede'].id,
            'movement_type': 'in',
            'quantity': 45,
            'notes': 'Notas actualizadas'
        }
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        movement.refresh_from_db()
        assert movement.quantity == 45
        assert movement.notes == 'Notas actualizadas'

    def test_partial_update_movement(self, api_client_authenticated, test_data):
        """Prueba actualización parcial de un movimiento."""
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=55,
            notes='Notas parciales'
        )
        
        detail_url = reverse('inventorymovement-detail', kwargs={'pk': movement.id})
        payload = {'notes': 'Notas parcialmente actualizadas'}
        response = api_client_authenticated.patch(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        movement.refresh_from_db()
        assert movement.quantity == 55  # No cambió
        assert movement.notes == 'Notas parcialmente actualizadas'

    def test_delete_movement(self, api_client_authenticated, test_data):
        """Prueba eliminar un movimiento."""
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=25
        )
        
        detail_url = reverse('inventorymovement-detail', kwargs={'pk': movement.id})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 204
        assert not InventoryMovement.objects.filter(pk=movement.id).exists()

    def test_movements_pagination(self, api_client_authenticated, test_data):
        """Prueba la paginación para la lista de movimientos."""
        # Crear 30 movimientos para asegurar que la paginación funcione
        # Solo crear movimientos de entrada para evitar problemas de stock negativo
        for i in range(30):
            InventoryMovement.objects.create(
                product=test_data['product'],
                location=test_data['sede'],
                movement_type='in',  # Solo entradas
                quantity=i + 5,
                notes=f'Movimiento paginado {i}'
            )
        
        response = api_client_authenticated.get(self.movements_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert 'results' in response.data
        
        # Con PAGE_SIZE=25, debe devolver 25 items en la primera página
        assert len(response.data['results']) == 25
        assert response.data['count'] >= 30

    def test_stock_alerts_endpoint(self, api_client_authenticated, test_data):
        """Prueba el endpoint de alertas de stock."""
        # Crear stock bajo
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=5  # Menor al umbral por defecto de 10
        )
        
        # Crear producto sin stock
        category2 = Category.objects.create(name='Cat Alert Test')
        product2 = Product.objects.create(
            sku='ALT-TEST-001',
            name='Product Alert Test',
            unit='unidad',
            category=category2
        )
        InventoryStock.objects.create(
            product=product2,
            location=test_data['sede'],
            quantity=0
        )
        
        alerts_url = reverse('inventorymovement-stock-alerts')
        response = api_client_authenticated.get(alerts_url)
        assert response.status_code == 200, f"Error: {response.data}"
        
        # Verificar que tenemos alertas
        assert len(response.data) >= 2
        
        # Verificar tipos de alerta
        alert_types = [alert['alert_type'] for alert in response.data]
        assert 'low_stock' in alert_types
        assert 'out_of_stock' in alert_types

    def test_stock_alerts_custom_threshold(self, api_client_authenticated, test_data):
        """Prueba alertas de stock con umbral personalizado."""
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=15
        )
        
        alerts_url = reverse('inventorymovement-stock-alerts')
        response = api_client_authenticated.get(alerts_url, {'min_stock': 20})
        assert response.status_code == 200
        
        # Con umbral de 20, nuestro producto con 15 debe aparecer en alertas
        low_stock_alerts = [
            alert for alert in response.data 
            if alert['alert_type'] == 'low_stock'
        ]
        assert len(low_stock_alerts) >= 1

    def test_stock_alerts_filter_by_location(self, api_client_authenticated, test_data):
        """Prueba filtrar alertas de stock por ubicación."""
        # Crear stock bajo en sede
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=3
        )
        
        # Crear stock normal en bodega
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['bodega'],
            quantity=50
        )
        
        alerts_url = reverse('inventorymovement-stock-alerts')
        response = api_client_authenticated.get(alerts_url, {'location': test_data['sede'].id})
        assert response.status_code == 200
        
        # Solo deben aparecer alertas de la sede
        for alert in response.data:
            assert alert['location_id'] == test_data['sede'].id

    def test_expiry_alerts_endpoint(self, api_client_authenticated, test_data):
        """Prueba el endpoint de alertas de vencimiento."""
        # Crear movimiento con producto próximo a vencer
        near_expiry = date.today() + timedelta(days=15)
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=20,
            expiry_date=near_expiry
        )
        
        alerts_url = reverse('inventorymovement-expiry-alerts')
        response = api_client_authenticated.get(alerts_url)
        assert response.status_code == 200, f"Error: {response.data}"
        
        # Verificar que encontramos productos próximos a vencer
        near_expiry_alerts = [
            alert for alert in response.data 
            if alert['days_to_expiry'] <= 30
        ]
        assert len(near_expiry_alerts) >= 1

    def test_expiry_alerts_custom_days(self, api_client_authenticated, test_data):
        """Prueba alertas de vencimiento con días personalizados."""
        # Crear producto que vence en 45 días
        far_expiry = date.today() + timedelta(days=45)
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=25,
            expiry_date=far_expiry
        )
        
        alerts_url = reverse('inventorymovement-expiry-alerts')
        response = api_client_authenticated.get(alerts_url, {'days_ahead': 60})
        assert response.status_code == 200
        
        # Con 60 días debe aparecer nuestro producto
        alerts_found = [
            alert for alert in response.data 
            if alert['product_id'] == test_data['product'].id
        ]
        assert len(alerts_found) >= 1

    def test_expiry_alerts_filter_by_location(self, api_client_authenticated, test_data):
        """Prueba filtrar alertas de vencimiento por ubicación."""
        near_expiry = date.today() + timedelta(days=10)
        
        # Crear movimiento en sede con fecha próxima
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=30,
            expiry_date=near_expiry
        )
        
        # Crear movimiento en bodega con fecha lejana
        far_expiry = date.today() + timedelta(days=100)
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['bodega'],
            movement_type='in',
            quantity=40,
            expiry_date=far_expiry
        )
        
        alerts_url = reverse('inventorymovement-expiry-alerts')
        response = api_client_authenticated.get(alerts_url, {'location': test_data['sede'].id})
        assert response.status_code == 200
        
        # Solo deben aparecer alertas de la sede
        for alert in response.data:
            assert alert['location_id'] == test_data['sede'].id 
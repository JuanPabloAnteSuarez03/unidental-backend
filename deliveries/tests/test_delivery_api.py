import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from deliveries.models import Delivery
from sales.models import Sale, Customer, SaleItem
from inventory.models import Location, InventoryStock
from catalogs.models import Category, Product

User = get_user_model()


@pytest.fixture
def api_client_authenticated():
    """Fixture para un cliente API autenticado."""
    client = APIClient()
    user_data = {
        'username': 'testauthuser_deliveries',
        'password': 'Str0ngP@sswOrd!DELIVERY',
        'email': 'testauthuser_deliveries@example.com'
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
    # Crear categoría y producto
    category = Category.objects.create(
        name='Test Category Deliveries API', 
        description='For deliveries API tests'
    )
    product = Product.objects.create(
        sku='API-DELIVERY-001',
        name='Test Product API Deliveries',
        description='Product for API deliveries testing',
        unit='unidad',
        category=category
    )
    
    # Crear ubicaciones
    origin_location = Location.objects.create(
        name='Test Origin Location',
        type='bodega'
    )
    
    dest_location = Location.objects.create(
        name='Test Dest Location',
        type='bodega'
    )
    
    inventory_stock = InventoryStock.objects.create(
        product=product,
        location=origin_location,
        quantity=100
    )
    
    # Crear cliente
    customer = Customer.objects.create(
        name='Cliente API Test Deliveries',
        phone='123456789',
        email='cliente.deliveries@test.com',
        notes='Cliente para pruebas API deliveries'
    )
    
    # Crear venta
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
    
    return {
        'category': category,
        'product': product,
        'origin_location': origin_location,
        'dest_location': dest_location,
        'inventory_stock': inventory_stock,
        'customer': customer,
        'sale': sale,
        'sale_item': sale_item
    }


@pytest.mark.django_db
class TestDeliveryAPI:
    """Tests para la API de entregas."""

    def setup_method(self):
        self.deliveries_url = reverse('delivery-list')

    def test_create_delivery(self, api_client_authenticated, test_data):
        """Prueba crear una entrega vía API."""
        payload = {
            'sale': test_data['sale'].id,
            'origin_location': test_data['origin_location'].id,
            'dest_location': test_data['dest_location'].id,
            'status': 'pending'
        }
        
        response = api_client_authenticated.post(self.deliveries_url, payload, format='json')
        assert response.status_code == 201
        
        # Verificar que se creó la entrega
        assert 'id' in response.data or Delivery.objects.filter(sale=test_data['sale']).exists()
        
        if 'id' in response.data:
            delivery = Delivery.objects.get(id=response.data['id'])
        else:
            delivery = Delivery.objects.get(sale=test_data['sale'])
            
        assert delivery.sale == test_data['sale']
        assert delivery.origin_location == test_data['origin_location']
        assert delivery.dest_location == test_data['dest_location']
        assert delivery.status == 'pending'

    def test_create_delivery_duplicate_sale(self, api_client_authenticated, test_data):
        """Prueba crear entrega para venta que ya tiene entrega."""
        # Crear primera entrega
        Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        # Intentar crear segunda entrega para la misma venta
        payload = {
            'sale': test_data['sale'].id,
            'origin_location': test_data['origin_location'].id,
            'dest_location': test_data['dest_location'].id,
            'status': 'pending'
        }
        
        response = api_client_authenticated.post(self.deliveries_url, payload, format='json')
        assert response.status_code == 400
        assert 'sale' in response.data

    def test_create_delivery_same_locations(self, api_client_authenticated, test_data):
        """Prueba crear entrega con mismas ubicaciones de origen y destino."""
        payload = {
            'sale': test_data['sale'].id,
            'origin_location': test_data['origin_location'].id,
            'dest_location': test_data['origin_location'].id,  # Misma ubicación
            'status': 'pending'
        }
        
        response = api_client_authenticated.post(self.deliveries_url, payload, format='json')
        assert response.status_code == 400
        assert 'dest_location' in response.data

    def test_list_deliveries(self, api_client_authenticated, test_data):
        """Prueba listar entregas."""
        # Crear entrega de prueba
        Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        response = api_client_authenticated.get(self.deliveries_url)
        assert response.status_code == 200
        
        # Manejar posible paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            deliveries_data = response.data['results']
        else:
            deliveries_data = response.data
            
        assert len(deliveries_data) >= 1

    def test_retrieve_delivery(self, api_client_authenticated, test_data):
        """Prueba obtener una entrega específica."""
        delivery = Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        url = reverse('delivery-detail', args=[delivery.id])
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert response.data['id'] == delivery.id
        assert response.data['status'] == 'pending'

    def test_update_delivery(self, api_client_authenticated, test_data):
        """Prueba actualizar una entrega."""
        delivery = Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        # Crear nueva ubicación de destino
        new_dest = Location.objects.create(name='Nueva Clínica', type='bodega')
        
        url = reverse('delivery-detail', args=[delivery.id])
        payload = {
            'dest_location': new_dest.id
        }
        
        response = api_client_authenticated.patch(url, payload, format='json')
        assert response.status_code == 200
        
        delivery.refresh_from_db()
        assert delivery.dest_location == new_dest

    def test_delete_delivery(self, api_client_authenticated, test_data):
        """Prueba eliminar una entrega."""
        delivery = Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        url = reverse('delivery-detail', args=[delivery.id])
        response = api_client_authenticated.delete(url)
        assert response.status_code == 204
        
        with pytest.raises(Delivery.DoesNotExist):
            Delivery.objects.get(id=delivery.id)

    def test_update_status_action(self, api_client_authenticated, test_data):
        """Prueba la acción de actualizar estado."""
        delivery = Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        url = reverse('delivery-update-status', args=[delivery.id])
        payload = {'status': 'in_transit'}
        
        response = api_client_authenticated.patch(url, payload, format='json')
        assert response.status_code == 200
        
        delivery.refresh_from_db()
        assert delivery.status == 'in_transit'
        assert delivery.shipped_at is not None

    def test_mark_shipped_action(self, api_client_authenticated, test_data):
        """Prueba la acción de marcar como enviado."""
        delivery = Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        url = reverse('delivery-mark-shipped', args=[delivery.id])
        response = api_client_authenticated.post(url)
        assert response.status_code == 200
        
        delivery.refresh_from_db()
        assert delivery.status == 'in_transit'
        assert delivery.shipped_at is not None

    def test_mark_delivered_action(self, api_client_authenticated, test_data):
        """Prueba la acción de marcar como entregado."""
        delivery = Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        url = reverse('delivery-mark-delivered', args=[delivery.id])
        response = api_client_authenticated.post(url)
        assert response.status_code == 200
        
        delivery.refresh_from_db()
        assert delivery.status == 'delivered'
        assert delivery.shipped_at is not None
        assert delivery.delivered_at is not None

    def test_statistics_action(self, api_client_authenticated, test_data):
        """Prueba la acción de estadísticas."""
        # Crear varias entregas para estadísticas
        delivery1 = Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        # Crear segunda venta y entrega
        sale2 = Sale.objects.create(
            customer=test_data['customer'],
            sale_type='normal',
            should_invoice=True
        )
        SaleItem.objects.create(
            sale=sale2,
            product=test_data['product'],
            quantity=1,
            unit_price=Decimal('25000.00')
        )
        
        delivery2 = Delivery.objects.create(
            sale=sale2,
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='delivered',
            shipped_at=timezone.now() - timedelta(days=1),
            delivered_at=timezone.now()
        )
        
        url = reverse('delivery-statistics')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        stats = response.data
        assert 'total_deliveries' in stats
        assert 'pending_deliveries' in stats
        assert 'in_transit_deliveries' in stats
        assert 'delivered_deliveries' in stats
        assert stats['total_deliveries'] >= 2

    def test_location_summary_action(self, api_client_authenticated, test_data):
        """Prueba la acción de resumen por ubicación."""
        Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        url = reverse('delivery-location-summary')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        summaries = response.data
        assert isinstance(summaries, list)
        assert len(summaries) >= 1

    def test_overdue_action(self, api_client_authenticated, test_data):
        """Prueba la acción de entregas atrasadas."""
        # Crear entrega atrasada (más de 7 días)
        delivery = Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        # Modificar fecha de creación para que sea atrasada
        delivery.created_at = timezone.now() - timedelta(days=10)
        delivery.save()
        
        url = reverse('delivery-overdue')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        overdue_deliveries = response.data
        assert len(overdue_deliveries) >= 1

    def test_by_route_action(self, api_client_authenticated, test_data):
        """Prueba la acción de entregas por ruta."""
        Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        url = reverse('delivery-by-route')
        response = api_client_authenticated.get(
            url, 
            {'origin_location': test_data['origin_location'].id}
        )
        assert response.status_code == 200
        
        route_deliveries = response.data
        assert len(route_deliveries) >= 1

    def test_by_route_action_missing_param(self, api_client_authenticated, test_data):
        """Prueba la acción de entregas por ruta sin parámetro requerido."""
        url = reverse('delivery-by-route')
        response = api_client_authenticated.get(url)
        assert response.status_code == 400
        assert 'error' in response.data

    def test_filter_deliveries_by_status(self, api_client_authenticated, test_data):
        """Prueba filtrar entregas por estado."""
        # Crear entregas con diferentes estados
        delivery1 = Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        sale2 = Sale.objects.create(
            customer=test_data['customer'],
            sale_type='normal',
            should_invoice=True
        )
        SaleItem.objects.create(
            sale=sale2,
            product=test_data['product'],
            quantity=1,
            unit_price=Decimal('25000.00')
        )
        
        delivery2 = Delivery.objects.create(
            sale=sale2,
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='delivered',
            shipped_at=timezone.now() - timedelta(days=1),
            delivered_at=timezone.now()
        )
        
        # Filtrar por estado pendiente
        response = api_client_authenticated.get(
            self.deliveries_url, 
            {'status': 'pending'}
        )
        assert response.status_code == 200
        
        if isinstance(response.data, dict) and 'results' in response.data:
            deliveries_data = response.data['results']
        else:
            deliveries_data = response.data
        
        # Verificar que solo se devuelven entregas pendientes
        for delivery_data in deliveries_data:
            assert delivery_data['status'] == 'pending'

    def test_filter_deliveries_by_location(self, api_client_authenticated, test_data):
        """Prueba filtrar entregas por ubicación."""
        Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        response = api_client_authenticated.get(
            self.deliveries_url, 
            {'origin_location': test_data['origin_location'].id}
        )
        assert response.status_code == 200

    def test_search_deliveries(self, api_client_authenticated, test_data):
        """Prueba búsqueda de entregas."""
        Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        # Buscar por nombre de cliente
        response = api_client_authenticated.get(
            self.deliveries_url, 
            {'search': test_data['customer'].name[:5]}
        )
        assert response.status_code == 200

    def test_ordering_deliveries(self, api_client_authenticated, test_data):
        """Prueba ordenamiento de entregas."""
        Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='pending'
        )
        
        # Ordenar por ID descendente
        response = api_client_authenticated.get(
            self.deliveries_url, 
            {'ordering': '-id'}
        )
        assert response.status_code == 200

    def test_unauthorized_access(self):
        """Prueba acceso no autorizado."""
        client = APIClient()
        response = client.get(self.deliveries_url)
        assert response.status_code == 401

    def test_invalid_delivery_id(self, api_client_authenticated):
        """Prueba con ID de entrega inválido."""
        url = reverse('delivery-detail', args=[99999])
        response = api_client_authenticated.get(url)
        assert response.status_code == 404

    def test_update_delivered_delivery(self, api_client_authenticated, test_data):
        """Prueba actualizar entrega ya entregada."""
        delivery = Delivery.objects.create(
            sale=test_data['sale'],
            origin_location=test_data['origin_location'],
            dest_location=test_data['dest_location'],
            status='delivered',
            shipped_at=timezone.now() - timedelta(days=1),
            delivered_at=timezone.now()
        )
        
        url = reverse('delivery-detail', args=[delivery.id])
        payload = {'status': 'pending'}
        
        response = api_client_authenticated.patch(url, payload, format='json')
        assert response.status_code == 400 
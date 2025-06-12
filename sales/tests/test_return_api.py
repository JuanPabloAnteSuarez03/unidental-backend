import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from sales.models import Customer, Sale, SaleItem, Return, ReturnItem
from inventory.models import Location, InventoryStock
from catalogs.models import Category, Product

User = get_user_model()


@pytest.fixture
def api_client_authenticated():
    """Fixture para un cliente API autenticado."""
    client = APIClient()
    user_data = {
        'username': 'testauthuser_returns',
        'password': 'Str0ngP@sswOrd!RETURN',
        'email': 'testauthuser_returns@example.com'
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
        name='Test Category Returns API', 
        description='For returns API tests'
    )
    product = Product.objects.create(
        sku='API-RETURN-001',
        name='Test Product API Returns',
        description='Product for API returns testing',
        unit='unidad',
        category=category
    )
    
    # Crear ubicación y stock
    location = Location.objects.create(
        name='Test Location Returns API',
        type='bodega'
    )
    
    inventory_stock = InventoryStock.objects.create(
        product=product,
        location=location,
        quantity=100
    )
    
    # Crear cliente
    customer = Customer.objects.create(
        name='Cliente Returns API Test',
        phone='123456789',
        email='cliente.returns.api@test.com',
        notes='Cliente para pruebas API de devoluciones'
    )
    
    # Crear venta
    sale = Sale.objects.create(
        customer=customer,
        location=location,
        sale_type='normal',
        total_gross=Decimal('150000.00'),
        total_net=Decimal('150000.00')
    )
    
    # Crear item de venta
    sale_item = SaleItem.objects.create(
        sale=sale,
        product=product,
        quantity=5,
        unit_price=Decimal('30000.00')
    )
    
    return {
        'category': category,
        'product': product,
        'location': location,
        'inventory_stock': inventory_stock,
        'customer': customer,
        'sale': sale,
        'sale_item': sale_item
    }


@pytest.mark.django_db
class TestReturnAPI:
    """Tests para la API de devoluciones."""

    def setup_method(self):
        self.returns_url = reverse('sales:return-list')

    def test_create_return_basic(self, api_client_authenticated, test_data):
        """Prueba crear una devolución básica."""
        payload = {
            'original_sale': test_data['sale'].id,
            'customer': test_data['customer'].id,
            'location': test_data['location'].id,
            'reason': 'defective',
            'notes': 'Producto defectuoso'
        }
        
        response = api_client_authenticated.post(self.returns_url, payload, format='json')
        assert response.status_code == 201
        
        return_obj = Return.objects.get(id=response.data['id'])
        assert return_obj.original_sale == test_data['sale']
        assert return_obj.customer == test_data['customer']
        assert return_obj.location == test_data['location']
        assert return_obj.reason == 'defective'

    def test_create_return_with_items(self, api_client_authenticated, test_data):
        """Prueba crear una devolución con items."""
        payload = {
            'original_sale': test_data['sale'].id,
            'customer': test_data['customer'].id,
            'location': test_data['location'].id,
            'reason': 'defective',
            'notes': 'Producto defectuoso con items',
            'items': [
                {
                    'sale_item': test_data['sale_item'].id,
                    'product': test_data['product'].id,
                    'quantity_returned': 2,
                    'unit_price': '30000.00'
                }
            ]
        }
        
        response = api_client_authenticated.post(self.returns_url, payload, format='json')
        assert response.status_code == 201
        
        return_obj = Return.objects.get(id=response.data['id'])
        assert return_obj.items.count() == 1
        assert return_obj.total_amount == Decimal('60000.00')

    def test_create_anonymous_return(self, api_client_authenticated, test_data):
        """Prueba crear una devolución anónima."""
        payload = {
            'original_sale': test_data['sale'].id,
            'location': test_data['location'].id,
            'reason': 'customer_change',
            'notes': 'Cliente anónimo cambió de opinión'
        }
        
        response = api_client_authenticated.post(self.returns_url, payload, format='json')
        assert response.status_code == 201
        
        return_obj = Return.objects.get(id=response.data['id'])
        assert return_obj.customer is None

    def test_list_returns(self, api_client_authenticated, test_data):
        """Prueba listar devoluciones."""
        # Crear algunas devoluciones
        for i in range(3):
            Return.objects.create(
                original_sale=test_data['sale'],
                location=test_data['location'],
                reason='defective',
                notes=f'Devolución {i+1}'
            )
        
        response = api_client_authenticated.get(self.returns_url)
        assert response.status_code == 200
        
        # Manejar posible paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            returns_data = response.data['results']
        else:
            returns_data = response.data
            
        assert len(returns_data) >= 3

    def test_retrieve_return(self, api_client_authenticated, test_data):
        """Prueba obtener una devolución específica."""
        return_obj = Return.objects.create(
            original_sale=test_data['sale'],
            customer=test_data['customer'],
            location=test_data['location'],
            reason='defective',
            notes='Test detail'
        )
        
        url = reverse('sales:return-detail', args=[return_obj.id])
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert response.data['reason'] == 'defective'

    def test_update_return(self, api_client_authenticated, test_data):
        """Prueba actualizar una devolución."""
        return_obj = Return.objects.create(
            original_sale=test_data['sale'],
            location=test_data['location'],
            reason='defective',
            notes='Notas originales'
        )
        
        url = reverse('sales:return-detail', args=[return_obj.id])
        payload = {
            'notes': 'Notas actualizadas',
            'reason': 'wrong_item'
        }
        
        response = api_client_authenticated.patch(url, payload, format='json')
        assert response.status_code == 200
        
        return_obj.refresh_from_db()
        assert return_obj.notes == 'Notas actualizadas'
        assert return_obj.reason == 'wrong_item'

    def test_delete_return(self, api_client_authenticated, test_data):
        """Prueba eliminar una devolución."""
        return_obj = Return.objects.create(
            original_sale=test_data['sale'],
            location=test_data['location'],
            reason='defective'
        )
        
        url = reverse('sales:return-detail', args=[return_obj.id])
        response = api_client_authenticated.delete(url)
        assert response.status_code == 204
        
        with pytest.raises(Return.DoesNotExist):
            Return.objects.get(id=return_obj.id)

    def test_statistics_action(self, api_client_authenticated, test_data):
        """Prueba el endpoint de estadísticas."""
        # Crear devoluciones de prueba
        for reason in ['defective', 'wrong_item']:
            return_obj = Return.objects.create(
                original_sale=test_data['sale'],
                location=test_data['location'],
                reason=reason
            )
            ReturnItem.objects.create(
                return_obj=return_obj,
                sale_item=test_data['sale_item'],
                product=test_data['product'],
                quantity_returned=1,
                unit_price=Decimal('30000.00')
            )
        
        url = reverse('sales:return-statistics')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert 'total_returns' in response.data
        assert response.data['total_returns'] == 2

    def test_today_action(self, api_client_authenticated, test_data):
        """Prueba el endpoint de devoluciones de hoy."""
        Return.objects.create(
            original_sale=test_data['sale'],
            location=test_data['location'],
            reason='defective',
            return_date=date.today()
        )
        
        url = reverse('sales:return-today')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        if isinstance(response.data, dict) and 'results' in response.data:
            returns_data = response.data['results']
        else:
            returns_data = response.data
            
        assert len(returns_data) >= 1

    def test_by_location_action(self, api_client_authenticated, test_data):
        """Prueba el endpoint de devoluciones por ubicación."""
        return_obj = Return.objects.create(
            original_sale=test_data['sale'],
            location=test_data['location'],
            reason='defective'
        )
        ReturnItem.objects.create(
            return_obj=return_obj,
            sale_item=test_data['sale_item'],
            product=test_data['product'],
            quantity_returned=1,
            unit_price=Decimal('30000.00')
        )
        
        url = reverse('sales:return-by-location')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1


@pytest.mark.django_db
class TestReturnItemAPI:
    """Tests para la API de items de devolución."""

    def setup_method(self):
        self.return_items_url = reverse('sales:returnitem-list')

    def test_create_return_item(self, api_client_authenticated, test_data):
        """Prueba crear un item de devolución."""
        return_obj = Return.objects.create(
            original_sale=test_data['sale'],
            location=test_data['location'],
            reason='defective'
        )
        
        payload = {
            'return_obj': return_obj.id,
            'sale_item': test_data['sale_item'].id,
            'product': test_data['product'].id,
            'quantity_returned': 2,
            'unit_price': '30000.00'
        }
        
        initial_stock = test_data['inventory_stock'].quantity
        
        response = api_client_authenticated.post(self.return_items_url, payload, format='json')
        assert response.status_code == 201
        
        # Verificar que se creó el item
        return_item = ReturnItem.objects.get(id=response.data['id'])
        assert return_item.quantity_returned == 2
        assert return_item.subtotal == Decimal('60000.00')
        
        # Verificar que se actualizó el stock
        test_data['inventory_stock'].refresh_from_db()
        assert test_data['inventory_stock'].quantity == initial_stock + 2

    def test_list_return_items(self, api_client_authenticated, test_data):
        """Prueba listar items de devolución."""
        return_obj = Return.objects.create(
            original_sale=test_data['sale'],
            location=test_data['location'],
            reason='defective'
        )
        
        # Crear algunos items
        for i in range(3):
            ReturnItem.objects.create(
                return_obj=return_obj,
                sale_item=test_data['sale_item'],
                product=test_data['product'],
                quantity_returned=1,
                unit_price=Decimal('30000.00')
            )
        
        response = api_client_authenticated.get(self.return_items_url)
        assert response.status_code == 200
        
        if isinstance(response.data, dict) and 'results' in response.data:
            items_data = response.data['results']
        else:
            items_data = response.data
            
        assert len(items_data) >= 3

    def test_update_return_item(self, api_client_authenticated, test_data):
        """Prueba actualizar un item de devolución."""
        return_obj = Return.objects.create(
            original_sale=test_data['sale'],
            location=test_data['location'],
            reason='defective'
        )
        
        return_item = ReturnItem.objects.create(
            return_obj=return_obj,
            sale_item=test_data['sale_item'],
            product=test_data['product'],
            quantity_returned=1,
            unit_price=Decimal('30000.00')
        )
        
        url = reverse('sales:returnitem-detail', args=[return_item.id])
        payload = {
            'quantity_returned': 3
        }
        
        response = api_client_authenticated.patch(url, payload, format='json')
        assert response.status_code == 200
        
        return_item.refresh_from_db()
        assert return_item.quantity_returned == 3
        assert return_item.subtotal == Decimal('90000.00')

    def test_delete_return_item(self, api_client_authenticated, test_data):
        """Prueba eliminar un item de devolución."""
        return_obj = Return.objects.create(
            original_sale=test_data['sale'],
            location=test_data['location'],
            reason='defective'
        )
        
        return_item = ReturnItem.objects.create(
            return_obj=return_obj,
            sale_item=test_data['sale_item'],
            product=test_data['product'],
            quantity_returned=1,
            unit_price=Decimal('30000.00')
        )
        
        url = reverse('sales:returnitem-detail', args=[return_item.id])
        response = api_client_authenticated.delete(url)
        assert response.status_code == 204
        
        with pytest.raises(ReturnItem.DoesNotExist):
            ReturnItem.objects.get(id=return_item.id)

    def test_top_returned_products_action(self, api_client_authenticated, test_data):
        """Prueba el endpoint de productos más devueltos."""
        return_obj = Return.objects.create(
            original_sale=test_data['sale'],
            location=test_data['location'],
            reason='defective'
        )
        
        # Crear varios items del mismo producto
        for i in range(3):
            ReturnItem.objects.create(
                return_obj=return_obj,
                sale_item=test_data['sale_item'],
                product=test_data['product'],
                quantity_returned=1,
                unit_price=Decimal('30000.00')
            )
        
        url = reverse('sales:returnitem-top-returned-products')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1 
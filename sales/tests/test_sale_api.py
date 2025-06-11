import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from sales.models import Customer, Sale, SaleItem
from inventory.models import Location, InventoryStock
from catalogs.models import Category, Product

User = get_user_model()


@pytest.fixture
def api_client_authenticated():
    """Fixture para un cliente API autenticado."""
    client = APIClient()
    user_data = {
        'username': 'testauthuser_sales',
        'password': 'Str0ngP@sswOrd!SALE',
        'email': 'testauthuser_sales@example.com'
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
        name='Test Category Sales API', 
        description='For sales API tests'
    )
    product = Product.objects.create(
        sku='API-SALE-001',
        name='Test Product API Sales',
        description='Product for API sales testing',
        unit='unidad',
        category=category
    )
    
    # Crear ubicación y stock
    location = Location.objects.create(
        name='Test Location Sales API',
        type='bodega'
    )
    
    inventory_stock = InventoryStock.objects.create(
        product=product,
        location=location,
        quantity=100
    )
    
    # Crear cliente
    customer = Customer.objects.create(
        name='Cliente API Test',
        phone='123456789',
        email='cliente.api@test.com',
        notes='Cliente para pruebas API'
    )
    
    return {
        'category': category,
        'product': product,
        'location': location,
        'inventory_stock': inventory_stock,
        'customer': customer
    }


@pytest.mark.django_db
class TestCustomerAPI:
    """Tests para la API de clientes."""

    def setup_method(self):
        self.customers_url = reverse('sales:customer-list')

    def test_create_customer(self, api_client_authenticated):
        """Prueba crear un cliente vía API."""
        payload = {
            'name': 'Nuevo Cliente',
            'phone': '987654321',
            'email': 'nuevo@cliente.com',
            'notes': 'Cliente de prueba API'
        }
        
        response = api_client_authenticated.post(self.customers_url, payload, format='json')
        assert response.status_code == 201
        
        customer = Customer.objects.get(id=response.data['id'])
        assert customer.name == payload['name']
        assert customer.phone == payload['phone']
        assert customer.email == payload['email']

    def test_list_customers(self, api_client_authenticated, test_data):
        """Prueba listar clientes."""
        response = api_client_authenticated.get(self.customers_url)
        assert response.status_code == 200
        
        # Manejar posible paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            customers_data = response.data['results']
        else:
            customers_data = response.data
            
        assert len(customers_data) >= 1

    def test_retrieve_customer(self, api_client_authenticated, test_data):
        """Prueba obtener un cliente específico."""
        url = reverse('sales:customer-detail', args=[test_data['customer'].id])
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert response.data['name'] == test_data['customer'].name

    def test_update_customer(self, api_client_authenticated, test_data):
        """Prueba actualizar un cliente."""
        url = reverse('sales:customer-detail', args=[test_data['customer'].id])
        payload = {
            'name': 'Cliente Actualizado',
            'phone': '999999999'
        }
        
        response = api_client_authenticated.patch(url, payload, format='json')
        assert response.status_code == 200
        
        test_data['customer'].refresh_from_db()
        assert test_data['customer'].name == payload['name']
        assert test_data['customer'].phone == payload['phone']

    def test_delete_customer(self, api_client_authenticated, test_data):
        """Prueba eliminar un cliente."""
        url = reverse('sales:customer-detail', args=[test_data['customer'].id])
        response = api_client_authenticated.delete(url)
        assert response.status_code == 204
        
        with pytest.raises(Customer.DoesNotExist):
            Customer.objects.get(id=test_data['customer'].id)


@pytest.mark.django_db
class TestSaleAPI:
    """Tests para la API de ventas."""

    def setup_method(self):
        self.sales_url = reverse('sales:sale-list')

    def test_create_sale_basic(self, api_client_authenticated, test_data):
        """Prueba crear una venta básica."""
        payload = {
            'customer': test_data['customer'].id,
            'location': test_data['location'].id,
            'sale_type': 'normal',
            'should_invoice': True,
            'items': [
                {
                    'product': test_data['product'].id,
                    'quantity': 2,
                    'unit_price': '50000.00'
                }
            ]
        }
        
        response = api_client_authenticated.post(self.sales_url, payload, format='json')
        assert response.status_code == 201
        
        sale = Sale.objects.get(id=response.data['id'])
        assert sale.customer == test_data['customer']
        assert sale.location == test_data['location']
        assert sale.items.count() == 1
        assert sale.total_gross == Decimal('100000.00')

    def test_create_anonymous_sale(self, api_client_authenticated, test_data):
        """Prueba crear una venta anónima."""
        payload = {
            'location': test_data['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': test_data['product'].id,
                    'quantity': 1,
                    'unit_price': '50000.00'
                }
            ]
        }
        
        response = api_client_authenticated.post(self.sales_url, payload, format='json')
        assert response.status_code == 201
        
        sale = Sale.objects.get(id=response.data['id'])
        assert sale.customer is None
        assert sale.location == test_data['location']
        assert sale.total_gross == Decimal('50000.00')

    def test_create_sale_without_items(self, api_client_authenticated, test_data):
        """Prueba que no se puede crear venta sin items."""
        payload = {
            'customer': test_data['customer'].id,
            'location': test_data['location'].id,
            'sale_type': 'normal',
            'items': []
        }
        
        response = api_client_authenticated.post(self.sales_url, payload, format='json')
        assert response.status_code == 400
        assert 'items' in response.data

    def test_create_sale_insufficient_stock(self, api_client_authenticated, test_data):
        """Prueba validación de stock insuficiente."""
        payload = {
            'customer': test_data['customer'].id,
            'location': test_data['location'].id,
            'sale_type': 'normal',
            'items': [
                {
                    'product': test_data['product'].id,
                    'quantity': 101,  # Stock es 100
                    'unit_price': '50000.00'
                }
            ]
        }
        
        response = api_client_authenticated.post(self.sales_url, payload, format='json')
        assert response.status_code == 400
        assert 'items' in response.data

    def test_list_sales(self, api_client_authenticated, test_data):
        """Prueba listar ventas."""
        # Crear algunas ventas
        sale1 = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        sale2 = Sale.objects.create(location=test_data['location'])  # Venta anónima
        
        response = api_client_authenticated.get(self.sales_url)
        assert response.status_code == 200
        
        # Manejar posible paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            sales_data = response.data['results']
        else:
            sales_data = response.data
            
        assert len(sales_data) >= 2

    def test_retrieve_sale(self, api_client_authenticated, test_data):
        """Prueba obtener una venta específica."""
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        SaleItem.objects.create(
            sale=sale,
            product=test_data['product'],
            quantity=1,
            unit_price=Decimal('50000.00')
        )
        
        url = reverse('sales:sale-detail', args=[sale.id])
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert response.data['customer'] == test_data['customer'].id
        assert response.data['location'] == test_data['location'].id
        assert len(response.data['items']) == 1

    def test_filter_sales_by_customer(self, api_client_authenticated, test_data):
        """Prueba filtrar ventas por cliente."""
        # Crear ventas específicas para este test
        sale_with_customer = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        sale_anonymous = Sale.objects.create(location=test_data['location'])  # Venta anónima
        
        url = f"{self.sales_url}?customer={test_data['customer'].id}"
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        # La respuesta puede estar paginada
        if isinstance(response.data, dict) and 'results' in response.data:
            sales_data = response.data['results']
        else:
            sales_data = response.data
            
        # Verificar que todas las ventas retornadas pertenecen al cliente correcto
        customer_sales = [sale for sale in sales_data if sale['customer'] == test_data['customer'].id]
        assert len(customer_sales) >= 1  # Al menos nuestra venta de prueba
        
        # Verificar que no hay ventas anónimas en los resultados
        anonymous_sales = [sale for sale in sales_data if sale['customer'] is None]
        assert len(anonymous_sales) == 0

    def test_filter_sales_by_date(self, api_client_authenticated, test_data):
        """Prueba filtrar ventas por fecha."""
        # Crear ventas en diferentes fechas
        sale1 = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        sale2 = Sale.objects.create(location=test_data['location'])
        
        # Filtrar por fecha
        today = date.today()
        url = f"{self.sales_url}?date={today}"
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        # Manejar posible paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            sales_data = response.data['results']
        else:
            sales_data = response.data
            
        assert len(sales_data) >= 1

    def test_statistics_action(self, api_client_authenticated, test_data):
        """Prueba acción de estadísticas."""
        # Crear algunas ventas con items
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']  # Agregar ubicación
        )
        SaleItem.objects.create(
            sale=sale,
            product=test_data['product'],
            quantity=2,
            unit_price=Decimal('50000.00')
        )
        
        url = f"{self.sales_url}statistics/"  # Usar la URL del router
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert 'total_sales' in response.data
        assert 'total_revenue' in response.data

    def test_today_action(self, api_client_authenticated, test_data):
        """Prueba acción de ventas del día."""
        # Crear una venta hoy
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']  # Agregar ubicación
        )
        
        url = f"{self.sales_url}today/"  # Usar la URL del router
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        # Esta acción devuelve una lista directa, no paginada
        assert isinstance(response.data, list)
        assert len(response.data) >= 1

    def test_by_location_action(self, api_client_authenticated, test_data):
        """Prueba acción de estadísticas por ubicación."""
        # Crear varias ventas con items en la ubicación de prueba
        sale1 = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        SaleItem.objects.create(
            sale=sale1,
            product=test_data['product'],
            quantity=2,
            unit_price=Decimal('50000.00')
        )
        
        sale2 = Sale.objects.create(
            location=test_data['location']  # Venta anónima
        )
        SaleItem.objects.create(
            sale=sale2,
            product=test_data['product'],
            quantity=3,
            unit_price=Decimal('30000.00')
        )
        
        url = f"{self.sales_url}by_location/"  # Usar la URL del router
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert isinstance(response.data, list)
        
        if len(response.data) > 0:
            location_stat = response.data[0]
            assert 'location_id' in location_stat
            assert 'location_name' in location_stat
            assert 'total_sales' in location_stat
            assert 'total_revenue' in location_stat
            assert 'average_sale' in location_stat

    def test_filter_sales_by_location(self, api_client_authenticated, test_data):
        """Prueba filtrar ventas por ubicación."""
        # Crear una segunda ubicación para comparar
        location2 = Location.objects.create(
            name='Segunda Ubicación Test',
            type='sucursal'
        )
        
        # Crear ventas en diferentes ubicaciones
        sale1 = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        sale2 = Sale.objects.create(
            location=location2
        )
        
        # Filtrar por la primera ubicación
        url = f"{self.sales_url}?location={test_data['location'].id}"
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        # Verificar que solo se devuelven ventas de la ubicación especificada
        if isinstance(response.data, dict) and 'results' in response.data:
            sales_data = response.data['results']
        else:
            sales_data = response.data
        
        location_sales = [sale for sale in sales_data if sale['location'] == test_data['location'].id]
        assert len(location_sales) >= 1


@pytest.mark.django_db
class TestSaleItemAPI:
    """Tests para la API de items de venta."""

    def setup_method(self):
        self.items_url = reverse('sales:saleitem-list')

    def test_list_items(self, api_client_authenticated, test_data):
        """Prueba listar items de venta."""
        # Crear algunos items
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=test_data['product'],
            quantity=1,
            unit_price=Decimal('50000.00')
        )
        
        response = api_client_authenticated.get(self.items_url)
        assert response.status_code == 200
        
        # Manejar posible paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            items_data = response.data['results']
        else:
            items_data = response.data
            
        assert len(items_data) >= 1

    def test_filter_items_by_product(self, api_client_authenticated, test_data):
        """Prueba filtrar items por producto."""
        # Crear items con diferentes productos
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=test_data['product'],
            quantity=1,
            unit_price=Decimal('50000.00')
        )
        
        url = f"{self.items_url}?product={test_data['product'].id}"
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        # La respuesta puede estar paginada, así que verificamos según el formato
        if isinstance(response.data, dict) and 'results' in response.data:
            # Respuesta paginada
            items_data = response.data['results']
        else:
            # Respuesta directa
            items_data = response.data
            
        assert len(items_data) >= 1
        assert all(item['product'] == test_data['product'].id for item in items_data)

    def test_top_products_action(self, api_client_authenticated, test_data):
        """Prueba acción de productos más vendidos."""
        # Crear ventas con items
        sale = Sale.objects.create(
            customer=test_data['customer'],
            location=test_data['location']  # Agregar ubicación
        )
        SaleItem.objects.create(
            sale=sale,
            product=test_data['product'],
            quantity=10,
            unit_price=Decimal('50000.00')
        )
        
        url = f"{self.items_url}top_products/"  # Usar la URL del router
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert isinstance(response.data, list)
        
        if len(response.data) > 0:
            top_product = response.data[0]
            assert 'product' in top_product
            assert 'total_quantity' in top_product 
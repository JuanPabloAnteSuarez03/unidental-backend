import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from purchases.models import PurchaseOrder, PurchaseOrderItem
from suppliers.models import Supplier, PurchaseOption
from inventory.models import Location
from catalogs.models import Category, Product

User = get_user_model()


@pytest.fixture
def api_client_authenticated():
    """Fixture para un cliente API autenticado."""
    client = APIClient()
    user_data = {
        'username': 'testauthuser_purchases',
        'password': 'Str0ngP@sswOrd!PUR',
        'email': 'testauthuser_purchases@example.com'
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
        name='Test Category Purchases API', 
        description='For purchases API tests'
    )
    product = Product.objects.create(
        sku='API-PUR-001',
        name='Test Product API Purchases',
        description='Product for API purchases testing',
        unit='caja',
        category=category
    )
    
    # Crear proveedor
    supplier = Supplier.objects.create(
        name='Proveedor API Test',
        contact_name='Ana García',
        phone='123456789',
        email='proveedor.api@test.com'
    )
    
    # Crear opciones de compra
    purchase_option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Marca API Test',
        purchase_price=Decimal('35000.00')
    )
    
    # Crear ubicaciones
    sede = Location.objects.create(
        name='Sede API Test', 
        type='sede', 
        address='API Test Address'
    )
    bodega = Location.objects.create(
        name='Bodega API Test', 
        type='bodega', 
        address='API Test Warehouse'
    )
    
    return {
        'category': category,
        'product': product,
        'supplier': supplier,
        'purchase_option': purchase_option,
        'sede': sede,
        'bodega': bodega
    }


@pytest.mark.django_db
class TestPurchaseOrderAPI:
    def setup_method(self):
        self.orders_url = reverse('purchaseorder-list')

    def test_create_purchase_order_basic(self, api_client_authenticated, test_data):
        """Prueba crear una orden de compra básica."""
        payload = {
            'supplier': test_data['supplier'].id,
            'destination': test_data['sede'].id,
            'order_date': str(date.today()),
            'notes': 'Orden de prueba API',
            'items': [
                {
                    'purchase_option': test_data['purchase_option'].id,
                    'quantity_requested': 10,
                    'unit_price': 35000.00
                }
            ]
        }
        
        response = api_client_authenticated.post(self.orders_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        
        # Verificar que se creó la orden
        order = PurchaseOrder.objects.get(id=response.data['id'])
        assert order.supplier == test_data['supplier']
        assert order.destination == test_data['sede']
        assert order.status == 'pending'
        assert order.items.count() == 1

    def test_create_purchase_order_multiple_items(self, api_client_authenticated, test_data):
        """Prueba crear orden con múltiples items."""
        # Crear otra opción de compra
        product2 = Product.objects.create(
            sku='API-PUR-002',
            name='Test Product 2',
            unit='unidad',
            category=test_data['category']
        )
        option2 = PurchaseOption.objects.create(
            product=product2,
            supplier=test_data['supplier'],
            brand='Marca 2',
            purchase_price=Decimal('50000.00')
        )
        
        payload = {
            'supplier': test_data['supplier'].id,
            'destination': test_data['bodega'].id,
            'notes': 'Orden múltiple',
            'items': [
                {
                    'purchase_option': test_data['purchase_option'].id,
                    'quantity_requested': 5,
                    'unit_price': 35000.00
                },
                {
                    'purchase_option': option2.id,
                    'quantity_requested': 3,
                    'unit_price': 50000.00
                }
            ]
        }
        
        response = api_client_authenticated.post(self.orders_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        
        order = PurchaseOrder.objects.get(id=response.data['id'])
        assert order.items.count() == 2
        assert order.total_items == 8
        assert order.total_amount == Decimal('325000.00')

    def test_create_purchase_order_without_items(self, api_client_authenticated, test_data):
        """Prueba que no se puede crear orden sin items."""
        payload = {
            'supplier': test_data['supplier'].id,
            'destination': test_data['sede'].id,
            'items': []
        }
        
        response = api_client_authenticated.post(self.orders_url, payload, format='json')
        assert response.status_code == 400
        assert 'items' in response.data

    def test_create_purchase_order_supplier_mismatch(self, api_client_authenticated, test_data):
        """Prueba validación de proveedor diferente."""
        # Crear otro proveedor y opción
        other_supplier = Supplier.objects.create(
            name='Otro Proveedor',
            contact_name='Luis Pérez',
            phone='987654321',
            email='otro@test.com'
        )
        other_option = PurchaseOption.objects.create(
            product=test_data['product'],
            supplier=other_supplier,
            brand='Otra Marca',
            purchase_price=Decimal('40000.00')
        )
        
        payload = {
            'supplier': test_data['supplier'].id,
            'destination': test_data['sede'].id,
            'items': [
                {
                    'purchase_option': other_option.id,  # Proveedor diferente
                    'quantity_requested': 5,
                    'unit_price': 40000.00
                }
            ]
        }
        
        response = api_client_authenticated.post(self.orders_url, payload, format='json')
        assert response.status_code == 400
        assert 'items' in response.data

    def test_create_purchase_order_unauthenticated(self, test_data):
        """Prueba que usuario no autenticado no puede crear órdenes."""
        client = APIClient()
        payload = {
            'supplier': test_data['supplier'].id,
            'destination': test_data['sede'].id,
            'items': [
                {
                    'purchase_option': test_data['purchase_option'].id,
                    'quantity_requested': 5,
                    'unit_price': 35000.00
                }
            ]
        }
        
        response = client.post(self.orders_url, payload, format='json')
        assert response.status_code == 401

    def test_list_purchase_orders(self, api_client_authenticated, test_data):
        """Prueba obtener lista de órdenes."""
        # Crear algunas órdenes
        order1 = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        order2 = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['bodega'],
            status='received'
        )
        
        response = api_client_authenticated.get(self.orders_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert len(response.data['results']) >= 2

    def test_filter_orders_by_status(self, api_client_authenticated, test_data):
        """Prueba filtrar órdenes por estado."""
        # Crear órdenes con diferentes estados
        PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='pending'
        )
        PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='received'
        )
        
        # Filtrar por pendientes
        response = api_client_authenticated.get(self.orders_url, {'status': 'pending'})
        assert response.status_code == 200
        for order in response.data['results']:
            assert order['status'] == 'pending'

    def test_filter_orders_by_supplier(self, api_client_authenticated, test_data):
        """Prueba filtrar órdenes por proveedor."""
        response = api_client_authenticated.get(
            self.orders_url, 
            {'supplier': test_data['supplier'].id}
        )
        assert response.status_code == 200
        for order in response.data['results']:
            assert order['supplier'] == test_data['supplier'].id

    def test_filter_orders_by_date_range(self, api_client_authenticated, test_data):
        """Prueba filtrar órdenes por rango de fechas."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        # Crear orden de ayer
        PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            order_date=yesterday
        )
        
        # Filtrar solo las de hoy
        response = api_client_authenticated.get(self.orders_url, {
            'order_date_from': str(today),
            'order_date_to': str(today)
        })
        assert response.status_code == 200

    def test_search_orders(self, api_client_authenticated, test_data):
        """Prueba búsqueda en órdenes."""
        PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            notes='Orden especial para API'
        )
        
        response = api_client_authenticated.get(self.orders_url, {'search': 'especial'})
        assert response.status_code == 200
        found = any('especial' in order.get('notes', '') for order in response.data['results'])
        assert found

    def test_retrieve_purchase_order(self, api_client_authenticated, test_data):
        """Prueba obtener detalle de orden."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            notes='Orden detalle'
        )
        PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('35000.00')
        )
        
        detail_url = reverse('purchaseorder-detail', kwargs={'pk': order.id})
        response = api_client_authenticated.get(detail_url)
        assert response.status_code == 200
        assert 'items' in response.data
        assert len(response.data['items']) == 1
        assert response.data['total_amount'] == '175000.00'

    def test_update_purchase_order(self, api_client_authenticated, test_data):
        """Prueba actualizar orden pendiente."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            notes='Original'
        )
        
        detail_url = reverse('purchaseorder-detail', kwargs={'pk': order.id})
        payload = {
            'supplier': test_data['supplier'].id,
            'destination': test_data['bodega'].id,  # Cambiar destino
            'notes': 'Actualizada'
        }
        
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        order.refresh_from_db()
        assert order.destination == test_data['bodega']
        assert order.notes == 'Actualizada'

    def test_cannot_update_received_order(self, api_client_authenticated, test_data):
        """Prueba que no se puede actualizar orden recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='received'
        )
        
        detail_url = reverse('purchaseorder-detail', kwargs={'pk': order.id})
        payload = {
            'supplier': test_data['supplier'].id,
            'destination': test_data['sede'].id,
            'notes': 'Intentando actualizar'
        }
        
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 400

    def test_delete_purchase_order(self, api_client_authenticated, test_data):
        """Prueba eliminar orden pendiente."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        detail_url = reverse('purchaseorder-detail', kwargs={'pk': order.id})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 204
        assert not PurchaseOrder.objects.filter(id=order.id).exists()

    def test_cannot_delete_received_order(self, api_client_authenticated, test_data):
        """Prueba que no se puede eliminar orden recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='received'
        )
        
        detail_url = reverse('purchaseorder-detail', kwargs={'pk': order.id})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 400

    def test_cancel_order_action(self, api_client_authenticated, test_data):
        """Prueba acción cancelar orden."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        cancel_url = reverse('purchaseorder-cancel', kwargs={'pk': order.id})
        response = api_client_authenticated.post(cancel_url)
        assert response.status_code == 200, f"Error: {response.data}"
        
        order.refresh_from_db()
        assert order.status == 'canceled'
        assert response.data['status'] == 'canceled'

    def test_cannot_cancel_received_order(self, api_client_authenticated, test_data):
        """Prueba que no se puede cancelar orden recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='received'
        )
        
        cancel_url = reverse('purchaseorder-cancel', kwargs={'pk': order.id})
        response = api_client_authenticated.post(cancel_url)
        assert response.status_code == 400

    def test_mark_received_action(self, api_client_authenticated, test_data):
        """Prueba acción marcar como recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        received_url = reverse('purchaseorder-mark-received', kwargs={'pk': order.id})
        response = api_client_authenticated.post(received_url)
        assert response.status_code == 200, f"Error: {response.data}"
        
        order.refresh_from_db()
        assert order.status == 'received'
        assert response.data['status'] == 'received'

    def test_cannot_mark_canceled_as_received(self, api_client_authenticated, test_data):
        """Prueba que no se puede marcar orden cancelada como recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='canceled'
        )
        
        received_url = reverse('purchaseorder-mark-received', kwargs={'pk': order.id})
        response = api_client_authenticated.post(received_url)
        assert response.status_code == 400

    def test_statistics_action(self, api_client_authenticated, test_data):
        """Prueba endpoint de estadísticas."""
        # Crear órdenes con diferentes estados
        PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='pending'
        )
        PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='received'
        )
        PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='canceled'
        )
        
        stats_url = reverse('purchaseorder-statistics')
        response = api_client_authenticated.get(stats_url)
        assert response.status_code == 200, f"Error: {response.data}"
        
        assert 'total_orders' in response.data
        assert 'pending_orders' in response.data
        assert 'received_orders' in response.data
        assert 'canceled_orders' in response.data
        assert response.data['total_orders'] >= 3

    def test_orders_pagination(self, api_client_authenticated, test_data):
        """Prueba paginación de órdenes."""
        # Crear 30 órdenes para probar paginación (PAGE_SIZE es 25)
        for i in range(30):
            PurchaseOrder.objects.create(
                supplier=test_data['supplier'],
                destination=test_data['sede']
            )
        
        response = api_client_authenticated.get(self.orders_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert 'results' in response.data
        
        assert len(response.data['results']) == 25
        assert response.data['count'] >= 30
        assert response.data['next'] is not None
        assert response.data['previous'] is None


@pytest.mark.django_db
class TestPurchaseOrderItemAPI:
    def setup_method(self):
        self.items_url = reverse('purchaseorderitem-list')

    def test_create_item_independently(self, api_client_authenticated, test_data):
        """Prueba crear item independientemente."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        payload = {
            'order': order.id,
            'purchase_option': test_data['purchase_option'].id,
            'quantity_requested': 8,
            'unit_price': 35000.00
        }
        
        response = api_client_authenticated.post(self.items_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        
        item = PurchaseOrderItem.objects.get(id=response.data['id'])
        assert item.order == order
        assert item.quantity_requested == 8
        assert item.line_total == Decimal('280000.00')

    def test_cannot_create_item_for_received_order(self, api_client_authenticated, test_data):
        """Prueba que no se puede crear item para orden recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede'],
            status='received'
        )
        
        payload = {
            'order': order.id,
            'purchase_option': test_data['purchase_option'].id,
            'quantity_requested': 5,
            'unit_price': 35000.00
        }
        
        response = api_client_authenticated.post(self.items_url, payload, format='json')
        assert response.status_code == 400

    def test_list_items(self, api_client_authenticated, test_data):
        """Prueba listar items."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('35000.00')
        )
        
        response = api_client_authenticated.get(self.items_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert len(response.data['results']) >= 1

    def test_filter_items_by_order(self, api_client_authenticated, test_data):
        """Prueba filtrar items por orden."""
        order1 = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        order2 = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['bodega']
        )
        
        PurchaseOrderItem.objects.create(
            order=order1,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('35000.00')
        )
        
        # Crear otra opción para el segundo item para evitar duplicate
        product2 = Product.objects.create(
            sku='API-FILTER-001',
            name='Product for Filter Test',
            unit='unidad',
            category=test_data['category']
        )
        option2 = PurchaseOption.objects.create(
            product=product2,
            supplier=test_data['supplier'],
            brand='Filter Brand',
            purchase_price=Decimal('35000.00')
        )
        
        PurchaseOrderItem.objects.create(
            order=order2,
            purchase_option=option2,
            quantity_requested=3,
            unit_price=Decimal('35000.00')
        )
        
        response = api_client_authenticated.get(self.items_url, {'order': order1.id})
        assert response.status_code == 200
        # Verificar que al menos uno de los items pertenece a la orden correcta
        found_order1_item = False
        for item in response.data['results']:
            # El campo podría ser 'order' o 'order_id' dependiendo del serializer
            if 'order' in item and item['order'] == order1.id:
                found_order1_item = True
            elif hasattr(PurchaseOrderItem.objects.get(id=item['id']), 'order'):
                db_item = PurchaseOrderItem.objects.get(id=item['id'])
                if db_item.order.id == order1.id:
                    found_order1_item = True
        assert found_order1_item

    def test_filter_items_by_product_name(self, api_client_authenticated, test_data):
        """Prueba filtrar items por nombre de producto."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('35000.00')
        )
        
        response = api_client_authenticated.get(
            self.items_url, 
            {'product_name': test_data['product'].name}
        )
        assert response.status_code == 200
        assert len(response.data['results']) >= 1

    def test_update_item(self, api_client_authenticated, test_data):
        """Prueba actualizar item de orden pendiente."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        item = PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('35000.00')
        )
        
        detail_url = reverse('purchaseorderitem-detail', kwargs={'pk': item.id})
        payload = {
            'order': order.id,
            'purchase_option': test_data['purchase_option'].id,
            'quantity_requested': 10,  # Cambiar cantidad
            'unit_price': 35000.00
        }
        
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        item.refresh_from_db()
        assert item.quantity_requested == 10

    def test_cannot_update_item_of_received_order(self, api_client_authenticated, test_data):
        """Prueba que no se puede actualizar item de orden recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        # Crear item mientras la orden está pendiente
        item = PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('35000.00')
        )
        
        # Cambiar estado a recibida
        order.status = 'received'
        order.save()
        
        detail_url = reverse('purchaseorderitem-detail', kwargs={'pk': item.id})
        payload = {
            'order': order.id,
            'purchase_option': test_data['purchase_option'].id,
            'quantity_requested': 10,
            'unit_price': 35000.00
        }
        
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 400

    def test_delete_item(self, api_client_authenticated, test_data):
        """Prueba eliminar item de orden pendiente."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        item = PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('35000.00')
        )
        
        detail_url = reverse('purchaseorderitem-detail', kwargs={'pk': item.id})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 204
        assert not PurchaseOrderItem.objects.filter(id=item.id).exists()

    def test_cannot_delete_item_of_received_order(self, api_client_authenticated, test_data):
        """Prueba que no se puede eliminar item de orden recibida."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        # Crear item mientras la orden está pendiente
        item = PurchaseOrderItem.objects.create(
            order=order,
            purchase_option=test_data['purchase_option'],
            quantity_requested=5,
            unit_price=Decimal('35000.00')
        )
        
        # Cambiar estado a recibida
        order.status = 'received'
        order.save()
        
        detail_url = reverse('purchaseorderitem-detail', kwargs={'pk': item.id})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 400

    def test_alternative_brands_action(self, api_client_authenticated, test_data):
        """Prueba endpoint de marcas alternativas."""
        # Crear otra opción para el mismo producto
        PurchaseOption.objects.create(
            product=test_data['product'],
            supplier=test_data['supplier'],
            brand='Marca Alternativa',
            purchase_price=Decimal('40000.00')
        )
        
        alternatives_url = reverse('purchaseorderitem-alternative-brands')
        response = api_client_authenticated.get(alternatives_url)
        assert response.status_code == 200, f"Error: {response.data}"
        
        # Debe encontrar el producto con múltiples opciones
        found_product = False
        for product_data in response.data:
            if product_data['product_id'] == test_data['product'].id:
                found_product = True
                assert len(product_data['alternatives']) >= 2
        
        assert found_product

    def test_alternative_brands_filter_by_supplier(self, api_client_authenticated, test_data):
        """Prueba filtrar marcas alternativas por proveedor."""
        alternatives_url = reverse('purchaseorderitem-alternative-brands')
        response = api_client_authenticated.get(
            alternatives_url, 
            {'supplier': test_data['supplier'].id}
        )
        assert response.status_code == 200

    def test_items_pagination(self, api_client_authenticated, test_data):
        """Prueba paginación de items."""
        order = PurchaseOrder.objects.create(
            supplier=test_data['supplier'],
            destination=test_data['sede']
        )
        
        # Crear 30 productos y opciones diferentes para items únicos
        for i in range(30):
            product = Product.objects.create(
                sku=f'PAG-{i:03d}',
                name=f'Producto Paginación {i}',
                unit='unidad',
                category=test_data['category']
            )
            option = PurchaseOption.objects.create(
                product=product,
                supplier=test_data['supplier'],
                brand=f'Marca {i}',
                purchase_price=Decimal('10000.00')
            )
            PurchaseOrderItem.objects.create(
                order=order,
                purchase_option=option,
                quantity_requested=1,
                unit_price=Decimal('10000.00')
            )
        
        response = api_client_authenticated.get(self.items_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert 'results' in response.data
        
        assert len(response.data['results']) == 25
        assert response.data['count'] >= 30
        assert response.data['next'] is not None
        assert response.data['previous'] is None 
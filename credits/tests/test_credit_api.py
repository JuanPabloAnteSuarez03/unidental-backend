import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from credits.models import CreditAccount, CreditPayment
from sales.models import Customer, Sale, SaleItem
from inventory.models import Location, InventoryStock
from catalogs.models import Category, Product

User = get_user_model()


@pytest.fixture
def api_client_authenticated():
    """Fixture para un cliente API autenticado."""
    client = APIClient()
    user_data = {
        'username': 'testauthuser_credits',
        'password': 'Str0ngP@sswOrd!CREDIT',
        'email': 'testauthuser_credits@example.com'
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
        name='Test Category Credits API', 
        description='For credits API tests'
    )
    product = Product.objects.create(
        sku='API-CREDIT-001',
        name='Test Product API Credits',
        description='Product for API credits testing',
        unit='unidad',
        category=category
    )
    
    # Crear ubicación y stock
    location = Location.objects.create(
        name='Test Location Credits API',
        type='bodega'
    )
    
    inventory_stock = InventoryStock.objects.create(
        product=product,
        location=location,
        quantity=100
    )
    
    # Crear cliente
    customer = Customer.objects.create(
        name='Cliente API Credit Test',
        phone='123456789',
        email='cliente.api.credit@test.com',
        notes='Cliente para pruebas API de crédito'
    )
    
    # Crear venta
    sale = Sale.objects.create(
        customer=customer,
        location=location,
        sale_type='normal',
        total_gross=Decimal('100000.00'),
        total_net=Decimal('100000.00')
    )
    
    return {
        'category': category,
        'product': product,
        'location': location,
        'inventory_stock': inventory_stock,
        'customer': customer,
        'sale': sale
    }


@pytest.mark.django_db
class TestCreditAccountAPI:
    """Tests para la API de cuentas de crédito."""

    def setup_method(self):
        self.accounts_url = reverse('credits:creditaccount-list')

    def test_create_credit_account_basic(self, api_client_authenticated, test_data):
        """Prueba crear una cuenta de crédito vía API."""
        payload = {
            'sale': test_data['sale'].id,
            'original_amount': '75000.00',
            'due_date': (date.today() + timedelta(days=30)).isoformat()
        }
        
        response = api_client_authenticated.post(self.accounts_url, payload, format='json')
        assert response.status_code == 201
        
        credit_account = CreditAccount.objects.get(id=response.data['id'])
        assert credit_account.sale == test_data['sale']
        assert credit_account.original_amount == Decimal('75000.00')
        assert credit_account.remaining_amount == Decimal('75000.00')

    def test_create_credit_via_create_credit_action(self, api_client_authenticated, test_data):
        """Prueba crear crédito usando la acción create_credit."""
        url = reverse('credits:creditaccount-create-credit')
        payload = {
            'sale_id': test_data['sale'].id,
            'original_amount': '80000.00',
            'due_date': (date.today() + timedelta(days=45)).isoformat()
        }
        
        response = api_client_authenticated.post(url, payload, format='json')
        assert response.status_code == 201
        
        credit_account = CreditAccount.objects.get(sale=test_data['sale'])
        assert credit_account.original_amount == Decimal('80000.00')

    def test_create_credit_invalid_amount(self, api_client_authenticated, test_data):
        """Prueba validación de monto que excede el total de la venta."""
        url = reverse('credits:creditaccount-create-credit')
        payload = {
            'sale_id': test_data['sale'].id,
            'original_amount': '150000.00',  # Excede el total de la venta
        }
        
        response = api_client_authenticated.post(url, payload, format='json')
        assert response.status_code == 400
        assert 'original_amount' in response.data

    def test_create_credit_duplicate_sale(self, api_client_authenticated, test_data):
        """Prueba que no se puede crear doble crédito para la misma venta."""
        # Crear primer crédito
        CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('50000.00'),
            remaining_amount=Decimal('50000.00')
        )
        
        # Intentar crear segundo crédito
        url = reverse('credits:creditaccount-create-credit')
        payload = {
            'sale_id': test_data['sale'].id,
            'original_amount': '30000.00',
        }
        
        response = api_client_authenticated.post(url, payload, format='json')
        assert response.status_code == 400

    def test_list_credit_accounts(self, api_client_authenticated, test_data):
        """Prueba listar cuentas de crédito."""
        # Crear algunas cuentas
        credit1 = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('50000.00'),
            remaining_amount=Decimal('30000.00')
        )
        
        response = api_client_authenticated.get(self.accounts_url)
        assert response.status_code == 200
        
        # Manejar posible paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            accounts_data = response.data['results']
        else:
            accounts_data = response.data
            
        assert len(accounts_data) >= 1

    def test_retrieve_credit_account(self, api_client_authenticated, test_data):
        """Prueba obtener una cuenta de crédito específica."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('75000.00'),
            remaining_amount=Decimal('45000.00')
        )
        
        url = reverse('credits:creditaccount-detail', args=[credit_account.id])
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert response.data['id'] == credit_account.id
        assert response.data['customer_name'] == test_data['customer'].name

    def test_debt_summary_action(self, api_client_authenticated, test_data):
        """Prueba endpoint de resumen de deuda actual."""
        # Crear algunas cuentas de crédito con deuda pendiente
        credit1 = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('60000.00')
        )
        
        url = reverse('credits:creditaccount-debt-summary')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1
        
        # Verificar estructura de datos
        debt_entry = response.data[0]
        assert 'customer_id' in debt_entry
        assert 'customer_name' in debt_entry
        assert 'total_debt' in debt_entry
        assert 'overdue_debt' in debt_entry
        assert 'active_credits_count' in debt_entry

    def test_overdue_accounts_action(self, api_client_authenticated, test_data):
        """Prueba endpoint de cuentas vencidas."""
        # Crear cuenta vencida
        past_date = date.today() - timedelta(days=10)
        credit_overdue = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('80000.00'),
            remaining_amount=Decimal('40000.00'),
            due_date=past_date
        )
        
        url = reverse('credits:creditaccount-overdue-accounts')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        # Verificar que contiene cuentas vencidas
        if isinstance(response.data, dict) and 'results' in response.data:
            accounts_data = response.data['results']
        else:
            accounts_data = response.data
            
        assert len(accounts_data) >= 1

    def test_statistics_action(self, api_client_authenticated, test_data):
        """Prueba endpoint de estadísticas."""
        # Crear datos para estadísticas
        credit1 = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('25000.00')
        )
        
        url = reverse('credits:creditaccount-statistics')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        # Verificar estructura de estadísticas
        stats = response.data
        assert 'total_credits' in stats
        assert 'active_credits' in stats
        assert 'total_credit_amount' in stats
        assert 'remaining_debt' in stats
        assert 'collection_rate' in stats

    def test_payment_history_action(self, api_client_authenticated, test_data):
        """Prueba endpoint de historial de pagos."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        # Crear algunos pagos
        payment1 = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('30000.00')
        )
        payment2 = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('20000.00')
        )
        
        url = reverse('credits:creditaccount-payment-history', args=[credit_account.id])
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_filter_accounts_by_customer(self, api_client_authenticated, test_data):
        """Prueba filtrar cuentas por cliente."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('50000.00'),
            remaining_amount=Decimal('25000.00')
        )
        
        url = f"{self.accounts_url}?sale__customer={test_data['customer'].id}"
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        # Manejar posible paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            accounts_data = response.data['results']
        else:
            accounts_data = response.data
            
        assert len(accounts_data) >= 1

    def test_filter_accounts_by_status(self, api_client_authenticated, test_data):
        """Prueba filtrar cuentas por estado de pago."""
        # Crear cuenta con deuda pendiente
        credit_pending = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('50000.00')
        )
        
        url = f"{self.accounts_url}?paid_status=pending"
        response = api_client_authenticated.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
class TestCreditPaymentAPI:
    """Tests para la API de pagos de crédito."""

    def setup_method(self):
        self.payments_url = reverse('credits:creditpayment-list')

    def test_create_payment_basic(self, api_client_authenticated, test_data):
        """Prueba crear un pago vía API."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        payload = {
            'credit_account': credit_account.id,
            'amount_paid': '25000.00',
            'notes': 'Pago en efectivo'
        }
        
        response = api_client_authenticated.post(self.payments_url, payload, format='json')
        assert response.status_code == 201
        
        payment = CreditPayment.objects.get(id=response.data['id'])
        assert payment.credit_account == credit_account
        assert payment.amount_paid == Decimal('25000.00')
        assert payment.notes == 'Pago en efectivo'

    def test_register_payment_action(self, api_client_authenticated, test_data):
        """Prueba registrar pago usando la acción register_payment."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        url = reverse('credits:creditpayment-register-payment')
        payload = {
            'credit_account': credit_account.id,
            'amount_paid': '40000.00',
            'payment_date': date.today().isoformat(),
            'notes': 'Pago con transferencia'
        }
        
        response = api_client_authenticated.post(url, payload, format='json')
        assert response.status_code == 201
        
        # Verificar que se actualizó el saldo de la cuenta
        credit_account.refresh_from_db()
        assert credit_account.remaining_amount == Decimal('60000.00')

    def test_payment_exceeds_remaining_amount(self, api_client_authenticated, test_data):
        """Prueba validación de pago que excede el monto pendiente."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('30000.00')
        )
        
        payload = {
            'credit_account': credit_account.id,
            'amount_paid': '50000.00',  # Excede el monto pendiente
        }
        
        response = api_client_authenticated.post(self.payments_url, payload, format='json')
        assert response.status_code == 400
        assert 'amount_paid' in response.data

    def test_list_payments(self, api_client_authenticated, test_data):
        """Prueba listar pagos."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('35000.00')
        )
        
        response = api_client_authenticated.get(self.payments_url)
        assert response.status_code == 200
        
        # Manejar posible paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            payments_data = response.data['results']
        else:
            payments_data = response.data
            
        assert len(payments_data) >= 1

    def test_filter_payments_by_credit_account(self, api_client_authenticated, test_data):
        """Prueba filtrar pagos por cuenta de crédito."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('25000.00')
        )
        
        url = f"{self.payments_url}?credit_account={credit_account.id}"
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        
        # Manejar posible paginación
        if isinstance(response.data, dict) and 'results' in response.data:
            payments_data = response.data['results']
        else:
            payments_data = response.data
            
        assert len(payments_data) >= 1

    def test_recent_payments_action(self, api_client_authenticated, test_data):
        """Prueba endpoint de pagos recientes."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        # Crear pago reciente
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('30000.00'),
            payment_date=date.today()
        )
        
        url = reverse('credits:creditpayment-recent-payments')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_recent_payments_with_days_filter(self, api_client_authenticated, test_data):
        """Prueba endpoint de pagos recientes con filtro de días."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        # Crear pago de hace 5 días
        past_date = date.today() - timedelta(days=5)
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('20000.00'),
            payment_date=past_date
        )
        
        url = f"{reverse('credits:creditpayment-recent-payments')}?days=10"
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_update_payment(self, api_client_authenticated, test_data):
        """Prueba actualizar un pago."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('30000.00')
        )
        
        url = reverse('credits:creditpayment-detail', args=[payment.id])
        payload = {
            'notes': 'Pago actualizado con transferencia bancaria'
        }
        
        response = api_client_authenticated.patch(url, payload, format='json')
        assert response.status_code == 200
        
        payment.refresh_from_db()
        assert payment.notes == 'Pago actualizado con transferencia bancaria'

    def test_delete_payment(self, api_client_authenticated, test_data):
        """Prueba eliminar un pago."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('25000.00')
        )
        
        url = reverse('credits:creditpayment-detail', args=[payment.id])
        response = api_client_authenticated.delete(url)
        assert response.status_code == 204
        
        with pytest.raises(CreditPayment.DoesNotExist):
            CreditPayment.objects.get(id=payment.id) 
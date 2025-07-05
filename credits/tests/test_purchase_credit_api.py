import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from decimal import Decimal

from credits.models import CreditPurchaseAccount, CreditPurchasePayment
from suppliers.models import Supplier, PurchaseOption
from purchases.models import PurchaseOrder, PurchaseOrderItem
from inventory.models import Location
from catalogs.models import Category, Product

User = get_user_model()


# =====================================================
# FIXTURES
# =====================================================


@pytest.fixture
def api_client_authenticated():
    """Cliente API autenticado (Token) para pruebas."""
    client = APIClient()
    user_data = {
        'username': 'testauthuser_purchase_credits',
        'password': 'Str0ngP@sswOrd!PURCHASE',
        'email': 'testauthuser_purchase_credits@example.com'
    }
    # Limpiar usuario previo
    User.objects.filter(username=user_data['username']).delete()

    # Registrar
    try:
        register_url = reverse('user-list')
    except:
        register_url = "/api/auth/users/"
    client.post(register_url, user_data, format='json')

    # Login
    try:
        login_url = reverse('login')
    except:
        login_url = "/api/auth/token/login/"
    response = client.post(login_url, {
        'username': user_data['username'],
        'password': user_data['password']
    }, format='json')

    token = response.data['auth_token']
    client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    return client


@pytest.fixture
def purchase_test_data():
    """Crea datos necesarios para pruebas de crédito de compras."""
    # Categoría y producto
    category = Category.objects.create(name='Test Category Purchase Credits', description='For purchase credit tests')
    product = Product.objects.create(
        sku='PUR-CREDIT-001',
        name='Test Product Purchase Credits',
        description='Product for purchase credit tests',
        unit='unidad',
        category=category
    )

    # Proveedor y opción de compra
    supplier = Supplier.objects.create(name='Proveedor Test Credits', phone='111222333', email='proveedor@test.com')
    purchase_option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='GENERIC',
        purchase_price=Decimal('5000.00')
    )

    # Ubicación
    location = Location.objects.create(name='Bodega Central Pruebas', type='bodega')

    # Orden de compra con un ítem
    purchase_order = PurchaseOrder.objects.create(
        supplier=supplier,
        destination=location,
    )
    PurchaseOrderItem.objects.create(
        order=purchase_order,
        purchase_option=purchase_option,
        quantity_requested=10,
        unit_price=purchase_option.purchase_price
    )

    return {
        'category': category,
        'product': product,
        'supplier': supplier,
        'purchase_option': purchase_option,
        'location': location,
        'purchase_order': purchase_order
    }


# =====================================================
# TESTS DE CREDIT PURCHASE ACCOUNT
# =====================================================


@pytest.mark.django_db
class TestCreditPurchaseAccountAPI:

    def setup_method(self):
        self.accounts_url = reverse('credits:creditpurchaseaccount-list')

    def test_create_credit_purchase_account(self, api_client_authenticated, purchase_test_data):
        """Crear una cuenta de crédito de compra básica."""
        payload = {
            'purchase_order': purchase_test_data['purchase_order'].id,
            'original_amount': '50000.00',
            'payment_frequency': 'monthly',
            'payment_amount': '10000.00',
            'next_payment_date': (date.today() + timedelta(days=30)).isoformat()
        }
        response = api_client_authenticated.post(self.accounts_url, payload, format='json')
        assert response.status_code == 201
        account = CreditPurchaseAccount.objects.get(id=response.data['id'])
        assert account.purchase_order == purchase_test_data['purchase_order']
        assert account.original_amount == Decimal('50000.00')
        assert account.remaining_amount == Decimal('50000.00')

    def test_duplicate_credit_account(self, api_client_authenticated, purchase_test_data):
        """No se debe permitir doble crédito para la misma orden."""
        CreditPurchaseAccount.objects.create(
            purchase_order=purchase_test_data['purchase_order'],
            original_amount=Decimal('40000.00'),
            remaining_amount=Decimal('40000.00')
        )
        payload = {
            'purchase_order': purchase_test_data['purchase_order'].id,
            'original_amount': '20000.00'
        }
        response = api_client_authenticated.post(self.accounts_url, payload, format='json')
        assert response.status_code == 400
        assert 'purchase_order' in response.data or 'non_field_errors' in response.data

    def test_list_accounts(self, api_client_authenticated, purchase_test_data):
        CreditPurchaseAccount.objects.create(
            purchase_order=purchase_test_data['purchase_order'],
            original_amount=Decimal('30000.00'),
            remaining_amount=Decimal('30000.00')
        )
        response = api_client_authenticated.get(self.accounts_url)
        assert response.status_code == 200
        # Manejar paginación
        accounts_data = response.data.get('results', response.data)
        assert len(accounts_data) >= 1

    def test_retrieve_account(self, api_client_authenticated, purchase_test_data):
        account = CreditPurchaseAccount.objects.create(
            purchase_order=purchase_test_data['purchase_order'],
            original_amount=Decimal('45000.00'),
            remaining_amount=Decimal('45000.00')
        )
        url = reverse('credits:creditpurchaseaccount-detail', args=[account.id])
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert response.data['id'] == account.id

    def test_overdue_accounts_action(self, api_client_authenticated, purchase_test_data):
        overdue_date = date.today() - timedelta(days=5)
        account = CreditPurchaseAccount.objects.create(
            purchase_order=purchase_test_data['purchase_order'],
            original_amount=Decimal('40000.00'),
            remaining_amount=Decimal('40000.00'),
            next_payment_date=overdue_date
        )
        url = reverse('credits:creditpurchaseaccount-overdue-accounts')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert any(item['id'] == account.id for item in response.data)

    def test_statistics_action(self, api_client_authenticated, purchase_test_data):
        CreditPurchaseAccount.objects.create(
            purchase_order=purchase_test_data['purchase_order'],
            original_amount=Decimal('60000.00'),
            remaining_amount=Decimal('60000.00')
        )
        url = reverse('credits:creditpurchaseaccount-statistics')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        expected_keys = [
            'total_credits', 'active_credits', 'overdue_credits',
            'total_credit_amount', 'remaining_debt', 'overdue_debt',
            'recent_payments_amount', 'collection_rate'
        ]
        for key in expected_keys:
            assert key in response.data

    def test_payment_history_action(self, api_client_authenticated, purchase_test_data):
        account = CreditPurchaseAccount.objects.create(
            purchase_order=purchase_test_data['purchase_order'],
            original_amount=Decimal('50000.00'),
            remaining_amount=Decimal('50000.00')
        )
        payment = CreditPurchasePayment.objects.create(
            credit_account=account,
            amount_paid=Decimal('10000.00')
        )
        url = reverse('credits:creditpurchaseaccount-payment-history', args=[account.id])
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert any(p['id'] == payment.id for p in response.data)


# =====================================================
# TESTS DE CREDIT PURCHASE PAYMENT
# =====================================================


@pytest.mark.django_db
class TestCreditPurchasePaymentAPI:

    def setup_method(self):
        self.payments_url = reverse('credits:creditpurchasepayment-list')

    def test_create_payment(self, api_client_authenticated, purchase_test_data):
        account = CreditPurchaseAccount.objects.create(
            purchase_order=purchase_test_data['purchase_order'],
            original_amount=Decimal('40000.00'),
            remaining_amount=Decimal('40000.00')
        )
        payload = {
            'credit_account': account.id,
            'amount_paid': '15000.00',
            'payment_method': 'transferencia'
        }
        response = api_client_authenticated.post(self.payments_url, payload, format='json')
        assert response.status_code == 201
        payment = CreditPurchasePayment.objects.get(id=response.data['id'])
        assert payment.credit_account == account
        assert payment.amount_paid == Decimal('15000.00')
        # Verifica actualización de saldo
        account.refresh_from_db()
        assert account.remaining_amount == Decimal('25000.00')

    def test_register_payment_action(self, api_client_authenticated, purchase_test_data):
        account = CreditPurchaseAccount.objects.create(
            purchase_order=purchase_test_data['purchase_order'],
            original_amount=Decimal('20000.00'),
            remaining_amount=Decimal('20000.00')
        )
        url = reverse('credits:creditpurchasepayment-register-payment')
        payload = {
            'credit_account': account.id,
            'amount_paid': '5000.00',
            'payment_date': date.today().isoformat(),
            'payment_method': 'efectivo'
        }
        response = api_client_authenticated.post(url, payload, format='json')
        assert response.status_code == 201
        account.refresh_from_db()
        assert account.remaining_amount == Decimal('15000.00')

    def test_payment_exceeds_remaining_amount(self, api_client_authenticated, purchase_test_data):
        account = CreditPurchaseAccount.objects.create(
            purchase_order=purchase_test_data['purchase_order'],
            original_amount=Decimal('10000.00'),
            remaining_amount=Decimal('3000.00')
        )
        payload = {
            'credit_account': account.id,
            'amount_paid': '6000.00'
        }
        response = api_client_authenticated.post(self.payments_url, payload, format='json')
        assert response.status_code == 400
        assert 'amount_paid' in response.data

    def test_recent_payments_action(self, api_client_authenticated, purchase_test_data):
        account = CreditPurchaseAccount.objects.create(
            purchase_order=purchase_test_data['purchase_order'],
            original_amount=Decimal('50000.00'),
            remaining_amount=Decimal('50000.00')
        )
        CreditPurchasePayment.objects.create(
            credit_account=account,
            amount_paid=Decimal('8000.00'),
            payment_date=date.today()
        )
        url = reverse('credits:creditpurchasepayment-recent-payments')
        response = api_client_authenticated.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1 
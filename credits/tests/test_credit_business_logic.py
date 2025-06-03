import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from decimal import Decimal

from credits.models import CreditAccount, CreditPayment
from sales.models import Customer, Sale, SaleItem
from inventory.models import Location, InventoryStock
from catalogs.models import Category, Product

User = get_user_model()


@pytest.fixture
def test_user():
    """Fixture para crear un usuario de prueba."""
    return User.objects.create_user(
        username='testuser_credits',
        email='testuser_credits@example.com',
        password='TestPass123!'
    )


@pytest.fixture
def test_data():
    """Fixture para crear datos de prueba."""
    # Crear categoría y producto
    category = Category.objects.create(
        name='Test Category Credits', 
        description='For credits tests'
    )
    product = Product.objects.create(
        sku='CREDIT-TEST-001',
        name='Test Product Credits',
        description='Product for credits testing',
        unit='unidad',
        category=category
    )
    
    # Crear ubicación y stock
    location = Location.objects.create(
        name='Test Location Credits',
        type='bodega'
    )
    
    inventory_stock = InventoryStock.objects.create(
        product=product,
        location=location,
        quantity=100
    )
    
    # Crear cliente
    customer = Customer.objects.create(
        name='Cliente Credit Test',
        phone='123456789',
        email='cliente.credit@test.com',
        notes='Cliente para pruebas de crédito'
    )
    
    # Crear venta
    sale = Sale.objects.create(
        customer=customer,
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
class TestCreditAccountBusinessLogic:
    """Tests para la lógica de negocio de cuentas de crédito."""

    def test_create_credit_account_basic(self, test_data):
        """Prueba crear una cuenta de crédito básica."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('80000.00'),
            remaining_amount=Decimal('80000.00')
        )
        
        assert credit_account.sale == test_data['sale']
        assert credit_account.original_amount == Decimal('80000.00')
        assert credit_account.remaining_amount == Decimal('80000.00')
        assert credit_account.start_date == date.today()
        assert credit_account.due_date is None

    def test_credit_account_string_representation(self, test_data):
        """Prueba representación string de cuenta de crédito."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('50000.00'),
            remaining_amount=Decimal('30000.00')
        )
        
        expected = f"Crédito {credit_account.id} - {test_data['customer'].name} - $30000.00"
        assert str(credit_account) == expected

    def test_credit_account_with_due_date(self, test_data):
        """Prueba crear cuenta de crédito con fecha de vencimiento."""
        due_date = date.today() + timedelta(days=30)
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('75000.00'),
            remaining_amount=Decimal('75000.00'),
            due_date=due_date
        )
        
        assert credit_account.due_date == due_date

    def test_is_fully_paid_property(self, test_data):
        """Prueba propiedad is_fully_paid."""
        # Cuenta con deuda pendiente
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('50000.00')
        )
        assert credit_account.is_fully_paid is False
        
        # Cuenta completamente pagada
        credit_account.remaining_amount = Decimal('0.00')
        credit_account.save()
        assert credit_account.is_fully_paid is True

    def test_is_overdue_property(self, test_data):
        """Prueba propiedad is_overdue."""
        # Cuenta sin fecha de vencimiento
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('50000.00')
        )
        assert credit_account.is_overdue is False
        
        # Cuenta con fecha de vencimiento futura
        future_date = date.today() + timedelta(days=10)
        credit_account.due_date = future_date
        credit_account.save()
        assert credit_account.is_overdue is False
        
        # Cuenta vencida con deuda pendiente
        past_date = date.today() - timedelta(days=5)
        credit_account.due_date = past_date
        credit_account.save()
        assert credit_account.is_overdue is True
        
        # Cuenta vencida pero completamente pagada
        credit_account.remaining_amount = Decimal('0.00')
        credit_account.save()
        assert credit_account.is_overdue is False

    def test_total_paid_property(self, test_data):
        """Prueba propiedad total_paid."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('30000.00')
        )
        
        assert credit_account.total_paid == Decimal('70000.00')

    def test_calculate_remaining_amount(self, test_data):
        """Prueba cálculo automático del monto pendiente."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        # Crear algunos pagos
        CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('30000.00')
        )
        CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('20000.00')
        )
        
        # Recalcular monto pendiente
        credit_account.calculate_remaining_amount()
        
        assert credit_account.remaining_amount == Decimal('50000.00')


@pytest.mark.django_db
class TestCreditPaymentBusinessLogic:
    """Tests para la lógica de negocio de pagos de crédito."""

    def test_create_credit_payment_basic(self, test_data):
        """Prueba crear un pago de crédito básico."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('25000.00')
        )
        
        assert payment.credit_account == credit_account
        assert payment.amount_paid == Decimal('25000.00')
        assert payment.payment_date == date.today()

    def test_payment_string_representation(self, test_data):
        """Prueba representación string de pago."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('25000.00')
        )
        
        expected = f"Pago $25000.00 - Crédito {credit_account.id} - {date.today()}"
        assert str(payment) == expected

    def test_payment_updates_remaining_amount(self, test_data):
        """Prueba que el pago actualiza automáticamente el monto pendiente."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        initial_remaining = credit_account.remaining_amount
        
        # Crear pago
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('30000.00')
        )
        
        # Verificar que se actualizó el monto pendiente
        credit_account.refresh_from_db()
        assert credit_account.remaining_amount == initial_remaining - payment.amount_paid

    def test_multiple_payments(self, test_data):
        """Prueba múltiples pagos en una cuenta de crédito."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        # Crear múltiples pagos
        payments = [
            Decimal('20000.00'),
            Decimal('15000.00'),
            Decimal('25000.00')
        ]
        
        for amount in payments:
            CreditPayment.objects.create(
                credit_account=credit_account,
                amount_paid=amount
            )
        
        credit_account.refresh_from_db()
        expected_remaining = Decimal('100000.00') - sum(payments)
        assert credit_account.remaining_amount == expected_remaining

    def test_payment_with_notes(self, test_data):
        """Prueba crear pago con notas."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('50000.00'),
            notes='Pago parcial en efectivo'
        )
        
        assert payment.notes == 'Pago parcial en efectivo'


@pytest.mark.django_db
class TestCreditDataIntegrity:
    """Tests para la integridad de datos en créditos."""

    def test_unique_credit_account_per_sale(self, test_data):
        """Prueba que solo puede haber una cuenta de crédito por venta."""
        # Crear primera cuenta de crédito
        CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('50000.00'),
            remaining_amount=Decimal('50000.00')
        )
        
        # Intentar crear segunda cuenta para la misma venta
        with pytest.raises(IntegrityError):
            CreditAccount.objects.create(
                sale=test_data['sale'],
                original_amount=Decimal('30000.00'),
                remaining_amount=Decimal('30000.00')
            )

    def test_cascade_delete_sale_affects_credit_account(self, test_data):
        """Prueba eliminación en cascada de cuenta de crédito al eliminar venta."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('50000.00'),
            remaining_amount=Decimal('50000.00')
        )
        
        sale_id = test_data['sale'].id
        credit_account_id = credit_account.id
        
        # Eliminar venta
        test_data['sale'].delete()
        
        # Verificar que la cuenta de crédito también se eliminó
        with pytest.raises(CreditAccount.DoesNotExist):
            CreditAccount.objects.get(id=credit_account_id)

    def test_cascade_delete_credit_account_affects_payments(self, test_data):
        """Prueba eliminación en cascada de pagos al eliminar cuenta de crédito."""
        credit_account = CreditAccount.objects.create(
            sale=test_data['sale'],
            original_amount=Decimal('100000.00'),
            remaining_amount=Decimal('100000.00')
        )
        
        payment = CreditPayment.objects.create(
            credit_account=credit_account,
            amount_paid=Decimal('25000.00')
        )
        
        payment_id = payment.id
        credit_account.delete()
        
        # Verificar que el pago también se eliminó
        with pytest.raises(CreditPayment.DoesNotExist):
            CreditPayment.objects.get(id=payment_id) 
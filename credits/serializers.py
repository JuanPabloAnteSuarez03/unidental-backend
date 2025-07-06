from rest_framework import serializers
from decimal import Decimal
from .models import CreditAccount, CreditPayment
from sales.models import Sale
from sales.serializers import SaleSerializer
from purchases.models import PurchaseOrder
from .models import CreditPurchaseAccount, CreditPurchasePayment


class CreditPaymentSerializer(serializers.ModelSerializer):
    """Serializador para pagos de crédito."""
    
    class Meta:
        model = CreditPayment
        fields = [
            'id', 'credit_account', 'amount_paid', 'payment_date', 
            'notes', 'created_at'
        ]
        read_only_fields = ['created_at']

    def validate(self, data):
        """Valida que el pago no exceda el monto pendiente."""
        # Durante actualizaciones parciales, credit_account puede no estar en data
        credit_account = data.get('credit_account')
        if not credit_account and self.instance:
            credit_account = self.instance.credit_account
        
        amount_paid = data.get('amount_paid')
        
        # Solo validar si tenemos tanto credit_account como amount_paid
        if credit_account and amount_paid:
            if amount_paid > credit_account.remaining_amount:
                raise serializers.ValidationError({
                    'amount_paid': f'El monto pagado no puede exceder el monto pendiente: ${credit_account.remaining_amount}'
                })
        
        return data


class CreditAccountSerializer(serializers.ModelSerializer):
    """Serializador para cuentas de crédito."""
    
    sale_details = SaleSerializer(source='sale', read_only=True)
    payments = CreditPaymentSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='sale.customer.name', read_only=True)
    customer_phone = serializers.CharField(source='sale.customer.phone', read_only=True)
    customer_email = serializers.CharField(source='sale.customer.email', read_only=True)
    
    # Campos calculados - usando SerializerMethodField
    is_fully_paid = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    payments_made_count = serializers.SerializerMethodField()
    remaining_installments = serializers.SerializerMethodField()
    payment_progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = CreditAccount
        fields = [
            'id', 'sale', 'sale_details', 'customer_name', 'customer_phone', 
            'customer_email', 'original_amount', 'remaining_amount', 
            'start_date', 'due_date', 'payment_frequency', 'installments_count',
            'installment_amount', 'next_payment_date', 'created_at', 'updated_at',
            'payments', 'is_fully_paid', 'is_overdue', 'total_paid',
            'payments_made_count', 'remaining_installments', 'payment_progress_percentage'
        ]
        read_only_fields = ['created_at', 'updated_at', 'remaining_amount']

    def get_is_fully_paid(self, obj):
        """Obtiene si el crédito está completamente pagado."""
        return obj.is_fully_paid

    def get_is_overdue(self, obj):
        """Obtiene si el crédito está vencido."""
        return obj.is_overdue

    def get_total_paid(self, obj):
        """Obtiene el total pagado."""
        return obj.total_paid

    def get_payments_made_count(self, obj):
        """Obtiene el número de pagos realizados."""
        return obj.payments_made_count

    def get_remaining_installments(self, obj):
        """Obtiene el número de cuotas restantes."""
        return obj.remaining_installments

    def get_payment_progress_percentage(self, obj):
        """Obtiene el porcentaje de progreso de pagos."""
        return obj.payment_progress_percentage

    def validate_sale(self, value):
        """Valida que la venta no tenga ya una cuenta de crédito."""
        if hasattr(value, 'credit_account'):
            raise serializers.ValidationError(
                "Esta venta ya tiene una cuenta de crédito asociada."
            )
        return value

    def validate(self, data):
        """Valida que el monto original no exceda el total de la venta."""
        sale = data['sale']
        original_amount = data['original_amount']
        
        if original_amount > sale.total_net:
            raise serializers.ValidationError({
                'original_amount': f'El monto de crédito no puede exceder el total de la venta: ${sale.total_net}'
            })
        
        return data

    def create(self, validated_data):
        """Crea una cuenta de crédito y establece el monto pendiente inicial."""
        validated_data['remaining_amount'] = validated_data['original_amount']
        return super().create(validated_data)


class CreateCreditAccountSerializer(serializers.Serializer):
    """Serializador para crear cuenta de crédito desde una venta."""
    
    sale_id = serializers.IntegerField()
    original_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    due_date = serializers.DateField(required=False, allow_null=True)
    
    # Campos para cuotas (opcionales)
    payment_frequency = serializers.ChoiceField(
        choices=[
            ('weekly', 'Semanal'),
            ('biweekly', 'Quincenal'),
            ('monthly', 'Mensual'),
            ('quarterly', 'Trimestral'),
            ('custom', 'Personalizado'),
        ],
        default='monthly',
        required=False
    )
    installments_count = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    installment_amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        min_value=Decimal('0.01'), 
        required=False, 
        allow_null=True
    )
    next_payment_date = serializers.DateField(required=False, allow_null=True)
    initial_payment = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        min_value=Decimal('0.01'), 
        required=False, 
        allow_null=True,
        help_text="Monto del pago inicial al crear el crédito"
    )
    
    def validate_sale_id(self, value):
        """Valida que la venta exista y no tenga ya una cuenta de crédito."""
        try:
            sale = Sale.objects.get(id=value)
        except Sale.DoesNotExist:
            raise serializers.ValidationError("La venta especificada no existe.")
        
        if hasattr(sale, 'credit_account'):
            raise serializers.ValidationError(
                "Esta venta ya tiene una cuenta de crédito asociada."
            )
        
        return value

    def validate(self, data):
        """Valida que el monto no exceda el total de la venta y valida cuotas."""
        sale = Sale.objects.get(id=data['sale_id'])
        original_amount = data['original_amount']
        
        if original_amount > sale.total_net:
            raise serializers.ValidationError({
                'original_amount': f'El monto de crédito no puede exceder el total de la venta: ${sale.total_net}'
            })
        
        # Validar cuotas si están presentes
        installments_count = data.get('installments_count')
        installment_amount = data.get('installment_amount')
        
        if installments_count and installment_amount:
            total_installments = installments_count * installment_amount
            if total_installments != original_amount:
                raise serializers.ValidationError({
                    'installment_amount': f'El total de cuotas (${total_installments}) debe ser igual al monto original (${original_amount})'
                })
        
        # Si se especifica número de cuotas pero no el monto, calcularlo automáticamente
        if installments_count and not installment_amount:
            data['installment_amount'] = original_amount / installments_count
        
        # Validar pago inicial
        initial_payment = data.get('initial_payment')
        if initial_payment:
            if initial_payment >= original_amount:
                raise serializers.ValidationError({
                    'initial_payment': 'El pago inicial no puede ser mayor o igual al monto total del crédito'
                })
            
            # Si hay cuotas configuradas, recalcular el monto de cuotas con el saldo restante
            if installments_count and installment_amount:
                remaining_after_initial = original_amount - initial_payment
                expected_installment = remaining_after_initial / installments_count
                if abs(installment_amount - expected_installment) > Decimal('0.01'):
                    raise serializers.ValidationError({
                        'installment_amount': f'Con el pago inicial de ${initial_payment}, cada cuota debería ser ${expected_installment:.2f}'
                    })
            
            # Si hay cuotas pero no monto especificado, calcularlo con el saldo restante
            elif installments_count and not data.get('installment_amount'):
                remaining_after_initial = original_amount - initial_payment
                data['installment_amount'] = remaining_after_initial / installments_count
        
        return data

    def create(self, validated_data):
        """Crea la cuenta de crédito y registra el pago inicial si existe."""
        from django.db import transaction
        
        sale = Sale.objects.get(id=validated_data['sale_id'])
        initial_payment = validated_data.get('initial_payment')
        
        with transaction.atomic():
            # Crear la cuenta de crédito
            credit_account = CreditAccount.objects.create(
                sale=sale,
                original_amount=validated_data['original_amount'],
                remaining_amount=validated_data['original_amount'],
                due_date=validated_data.get('due_date'),
                payment_frequency=validated_data.get('payment_frequency', 'monthly'),
                installments_count=validated_data.get('installments_count'),
                installment_amount=validated_data.get('installment_amount'),
                next_payment_date=validated_data.get('next_payment_date')
            )
            
            # Si hay pago inicial, registrarlo automáticamente
            if initial_payment:
                from .models import CreditPayment
                from datetime import date
                
                CreditPayment.objects.create(
                    credit_account=credit_account,
                    amount_paid=initial_payment,
                    payment_date=date.today(),
                    notes="Pago inicial registrado automáticamente al crear el crédito"
                )
                
                # El remaining_amount se actualiza automáticamente por el método save() de CreditPayment
        
        return credit_account


class DebtSummarySerializer(serializers.Serializer):
    """Serializador para resumen de deuda actual."""
    
    customer_id = serializers.IntegerField()
    customer_name = serializers.CharField()
    customer_phone = serializers.CharField()
    customer_email = serializers.CharField()
    total_debt = serializers.DecimalField(max_digits=12, decimal_places=2)
    overdue_debt = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_credits_count = serializers.IntegerField()
    overdue_credits_count = serializers.IntegerField()


# =============================
# SERIALIZADORES PARA COMPRAS A CRÉDITO
# =============================

class CreditPurchasePaymentSerializer(serializers.ModelSerializer):
    """Serializador para abonos de crédito de compra."""
    class Meta:
        model = CreditPurchasePayment
        fields = [
            'id', 'credit_account', 'amount_paid', 'payment_date', 'payment_method',
            'reference_number', 'notes', 'created_at'
        ]
        read_only_fields = ['created_at']

    def validate(self, data):
        credit_account = data.get('credit_account') or (self.instance.credit_account if self.instance else None)
        amount_paid = data.get('amount_paid')
        if credit_account and amount_paid and amount_paid > credit_account.remaining_amount:
            raise serializers.ValidationError({
                'amount_paid': f'El monto pagado no puede exceder el monto pendiente: ${credit_account.remaining_amount}'
            })
        return data


class CreditPurchaseAccountSerializer(serializers.ModelSerializer):
    """Serializador para cuentas de crédito de compra."""

    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    payments = CreditPurchasePaymentSerializer(many=True, read_only=True)

    is_fully_paid = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()

    class Meta:
        model = CreditPurchaseAccount
        fields = [
            'id', 'purchase_order', 'supplier_name', 'original_amount', 'remaining_amount',
            'start_date', 'payment_frequency', 'next_payment_date', 'payment_amount', 'grace_days',
            'is_active', 'notes', 'created_at', 'updated_at',
            'payments', 'is_fully_paid', 'is_overdue', 'total_paid'
        ]
        read_only_fields = ['created_at', 'updated_at', 'remaining_amount']

    def get_is_fully_paid(self, obj):
        return obj.is_fully_paid

    def get_is_overdue(self, obj):
        return obj.is_overdue

    def get_total_paid(self, obj):
        return obj.total_paid

    def validate_purchase_order(self, value):
        if hasattr(value, 'credit_account'):
            raise serializers.ValidationError("Esta orden de compra ya tiene una cuenta de crédito asociada.")
        return value

    def create(self, validated_data):
        validated_data['remaining_amount'] = validated_data['original_amount']
        return super().create(validated_data) 
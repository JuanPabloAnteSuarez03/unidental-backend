from rest_framework import serializers
from decimal import Decimal
from .models import CreditAccount, CreditPayment
from sales.models import Sale
from sales.serializers import SaleSerializer


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
    
    class Meta:
        model = CreditAccount
        fields = [
            'id', 'sale', 'sale_details', 'customer_name', 'customer_phone', 
            'customer_email', 'original_amount', 'remaining_amount', 
            'start_date', 'due_date', 'created_at', 'updated_at',
            'payments', 'is_fully_paid', 'is_overdue', 'total_paid'
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
        """Valida que el monto no exceda el total de la venta."""
        sale = Sale.objects.get(id=data['sale_id'])
        original_amount = data['original_amount']
        
        if original_amount > sale.total_net:
            raise serializers.ValidationError({
                'original_amount': f'El monto de crédito no puede exceder el total de la venta: ${sale.total_net}'
            })
        
        return data

    def create(self, validated_data):
        """Crea la cuenta de crédito."""
        sale = Sale.objects.get(id=validated_data['sale_id'])
        
        credit_account = CreditAccount.objects.create(
            sale=sale,
            original_amount=validated_data['original_amount'],
            remaining_amount=validated_data['original_amount'],
            due_date=validated_data.get('due_date')
        )
        
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
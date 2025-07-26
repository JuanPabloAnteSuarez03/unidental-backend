from rest_framework import serializers
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Cash, CashMovement, CashTransfer
from inventory.models import Location
from sales.models import Sale
from purchases.models import PurchaseOrder


class CashSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Cash."""
    
    location_name = serializers.CharField(source='location.name', read_only=True)
    location_type = serializers.CharField(source='location.get_type_display', read_only=True)
    location_address = serializers.CharField(source='location.address', read_only=True)
    balance_formatted = serializers.SerializerMethodField()
    movements_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Cash
        fields = [
            'id', 'location', 'location_name', 'location_type', 'location_address',
            'balance', 'balance_formatted', 'is_active', 'movements_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']

    def get_balance_formatted(self, obj):
        """Retorna el saldo formateado con símbolo de moneda."""
        return f"${obj.balance:,.2f}"

    def get_movements_count(self, obj):
        """Retorna el número total de movimientos de esta caja."""
        return obj.movements.count()

    def validate_location(self, value):
        """Valida que la ubicación sea una sede y no tenga ya una caja asociada."""
        if value.type != 'sede':
            raise serializers.ValidationError("Solo se pueden crear cajas para sedes, no para bodegas.")
        
        # Verificar si ya existe una caja para esta sede (solo para nuevas cajas)
        if not self.instance and Cash.objects.filter(location=value).exists():
            raise serializers.ValidationError(f"Ya existe una caja para la sede '{value.name}'.")
        
        return value


class CashMovementSerializer(serializers.ModelSerializer):
    """Serializer para el modelo CashMovement."""
    
    cash_name = serializers.SerializerMethodField()
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    reference_type_display = serializers.CharField(source='get_reference_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    cancelled_by_name = serializers.SerializerMethodField()
    amount_formatted = serializers.SerializerMethodField()
    sale_info = serializers.SerializerMethodField()
    purchase_order_info = serializers.SerializerMethodField()
    
    class Meta:
        model = CashMovement
        fields = [
            'id', 'cash', 'cash_name', 'movement_type', 'movement_type_display',
            'amount', 'amount_formatted', 'reference_type', 'reference_type_display',
            'notes', 'status', 'status_display', 'sale', 'sale_info',
            'purchase_order', 'purchase_order_info', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'cancelled_by', 'cancelled_by_name',
            'cancelled_at', 'cancellation_reason'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'cancelled_by', 'cancelled_at'
        ]

    def get_cash_name(self, obj):
        return obj.cash.location.name if obj.cash and obj.cash.location else ""

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else ""

    def get_cancelled_by_name(self, obj):
        return obj.cancelled_by.username if obj.cancelled_by else ""

    def get_amount_formatted(self, obj):
        """Retorna el monto formateado según el tipo de movimiento."""
        if obj.movement_type == 'egreso':
            return f"-${obj.amount:,.2f}"
        elif obj.movement_type == 'ingreso':
            return f"+${obj.amount:,.2f}"
        else:  # ajuste
            return f"${obj.amount:,.2f}"

    def get_sale_info(self, obj):
        if obj.sale:
            return {
                'id': obj.sale.id,
                'total': str(getattr(obj.sale, 'total_net', '')),
                'customer': getattr(getattr(obj.sale, 'customer', None), 'name', 'Sin cliente'),
                'date': getattr(obj.sale, 'sale_date', '')
            }
        return None

    def get_purchase_order_info(self, obj):
        if obj.purchase_order:
            return {
                'id': obj.purchase_order.id,
                'supplier': getattr(getattr(obj.purchase_order, 'supplier', None), 'name', ''),
                'date': getattr(obj.purchase_order, 'order_date', ''),
                'status': obj.purchase_order.get_status_display() if hasattr(obj.purchase_order, 'get_status_display') else ''
            }
        return None

    def validate(self, data):
        """Validaciones personalizadas para el movimiento."""
        # Validar que el monto sea positivo
        if data.get('amount', 0) <= 0:
            raise serializers.ValidationError({
                'amount': 'El monto debe ser mayor a cero.'
            })

        # Validar saldo suficiente para egresos (solo para nuevos movimientos)
        if (data.get('movement_type') == 'egreso' and 
            data.get('status', 'active') == 'active' and 
            not self.instance):
            
            cash = data.get('cash')
            amount = data.get('amount', 0)
            
            if cash and not cash.has_sufficient_balance(amount):
                raise serializers.ValidationError({
                    'amount': f'Saldo insuficiente en {cash.location.name}. Saldo actual: ${cash.balance:,.2f}'
                })

        return data

    def create(self, validated_data):
        """Crear un nuevo movimiento de caja."""
        # Agregar el usuario que crea el movimiento
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)


class CashMovementCreateSerializer(serializers.ModelSerializer):
    """Serializer simplificado para crear movimientos de caja."""
    
    class Meta:
        model = CashMovement
        fields = [
            'cash', 'movement_type', 'amount', 'reference_type', 'notes',
            'sale', 'purchase_order'
        ]

    def validate(self, data):
        """Validaciones para creación de movimientos."""
        # Validar que el monto sea positivo
        if data.get('amount', 0) <= 0:
            raise serializers.ValidationError({
                'amount': 'El monto debe ser mayor a cero.'
            })

        # Validar saldo suficiente para egresos
        if data.get('movement_type') == 'egreso':
            cash = data.get('cash')
            amount = data.get('amount', 0)
            
            if cash and not cash.has_sufficient_balance(amount):
                raise serializers.ValidationError({
                    'amount': f'Saldo insuficiente en {cash.location.name}. Saldo actual: ${cash.balance:,.2f}'
                })

        return data

    def create(self, validated_data):
        """Crear movimiento con usuario."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)


class CashTransferSerializer(serializers.ModelSerializer):
    """Serializer para el modelo CashTransfer."""
    
    origin_cash_name = serializers.CharField(source='origin_cash.location.name', read_only=True)
    destination_cash_name = serializers.CharField(source='destination_cash.location.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    amount_formatted = serializers.SerializerMethodField()
    origin_movement_info = serializers.SerializerMethodField()
    destination_movement_info = serializers.SerializerMethodField()
    
    class Meta:
        model = CashTransfer
        fields = [
            'id', 'origin_cash', 'origin_cash_name', 'destination_cash', 'destination_cash_name',
            'amount', 'amount_formatted', 'notes', 'status', 'status_display',
            'origin_movement', 'origin_movement_info', 'destination_movement', 'destination_movement_info',
            'created_by', 'created_by_name', 'created_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'status', 'origin_movement', 'destination_movement',
            'created_by', 'created_at', 'completed_at'
        ]

    def get_amount_formatted(self, obj):
        """Retorna el monto formateado."""
        return f"${obj.amount:,.2f}"

    def get_origin_movement_info(self, obj):
        """Información del movimiento de salida."""
        if obj.origin_movement:
            return {
                'id': obj.origin_movement.id,
                'amount': str(obj.origin_movement.amount),
                'status': obj.origin_movement.get_status_display()
            }
        return None

    def get_destination_movement_info(self, obj):
        """Información del movimiento de entrada."""
        if obj.destination_movement:
            return {
                'id': obj.destination_movement.id,
                'amount': str(obj.destination_movement.amount),
                'status': obj.destination_movement.get_status_display()
            }
        return None

    def validate(self, data):
        """Validaciones para transferencias."""
        origin_cash = data.get('origin_cash')
        destination_cash = data.get('destination_cash')
        amount = data.get('amount', 0)

        # Validar que no sea la misma caja
        if origin_cash == destination_cash:
            raise serializers.ValidationError(
                "No se puede transferir dinero a la misma caja."
            )

        # Validar monto positivo
        if amount <= 0:
            raise serializers.ValidationError({
                'amount': 'El monto debe ser mayor a cero.'
            })

        # Validar saldo suficiente
        if origin_cash and not origin_cash.has_sufficient_balance(amount):
            raise serializers.ValidationError({
                'amount': f'Saldo insuficiente en {origin_cash.location.name}. Saldo actual: ${origin_cash.balance:,.2f}'
            })

        return data

    def create(self, validated_data):
        """Crear transferencia con usuario."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)


class CashTransferCreateSerializer(serializers.ModelSerializer):
    """Serializer simplificado para crear transferencias."""
    
    class Meta:
        model = CashTransfer
        fields = ['origin_cash', 'destination_cash', 'amount', 'notes']

    def validate(self, data):
        """Validaciones básicas para transferencias."""
        origin_cash = data.get('origin_cash')
        destination_cash = data.get('destination_cash')
        amount = data.get('amount', 0)

        if origin_cash == destination_cash:
            raise serializers.ValidationError(
                "No se puede transferir dinero a la misma caja."
            )

        if amount <= 0:
            raise serializers.ValidationError({
                'amount': 'El monto debe ser mayor a cero.'
            })

        if origin_cash and not origin_cash.has_sufficient_balance(amount):
            raise serializers.ValidationError({
                'amount': f'Saldo insuficiente en {origin_cash.location.name}. Saldo actual: ${origin_cash.balance:,.2f}'
            })

        return data

    def create(self, validated_data):
        """Crear y ejecutar transferencia."""
        request = self.context.get('request')
        user = request.user if request and hasattr(request, 'user') else None
        
        validated_data['created_by'] = user
        transfer = super().create(validated_data)
        
        # Ejecutar la transferencia automáticamente
        if user:
            transfer.execute_transfer(user)
        
        return transfer


class CashSummarySerializer(serializers.Serializer):
    """Serializer para resúmenes de caja."""
    
    total_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_balance_formatted = serializers.CharField()
    active_cashes_count = serializers.IntegerField()
    recent_movements_count = serializers.IntegerField()
    pending_transfers_count = serializers.IntegerField()
    
    def to_representation(self, instance):
        """Personalizar la representación del resumen."""
        data = super().to_representation(instance)
        # Asegura que total_balance sea Decimal antes de formatear
        total_balance = data.get('total_balance', 0)
        if isinstance(total_balance, str):
            try:
                total_balance = Decimal(total_balance)
            except (ValueError, TypeError):
                total_balance = Decimal('0.00')
        elif not isinstance(total_balance, Decimal):
            total_balance = Decimal(str(total_balance))
        
        data['total_balance_formatted'] = f"${total_balance:,.2f}"
        return data 
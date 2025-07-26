from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import PurchaseOrder, PurchaseOrderItem
from suppliers.models import Supplier, PurchaseOption
from suppliers.serializers import SupplierSerializer, PurchaseOptionSerializer
from inventory.models import Location
from inventory.serializers import LocationSerializer
from catalogs.models import Product
from .models import PurchaseOrderPayment


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer para items de orden de compra.
    """
    purchase_option_details = PurchaseOptionSerializer(source='purchase_option', read_only=True)
    line_total = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    product_name = serializers.CharField(source='purchase_option.product.name', read_only=True)
    product_sku = serializers.CharField(source='purchase_option.product.sku', read_only=True)
    brand = serializers.CharField(source='purchase_option.brand', read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id',
            'purchase_option',
            'purchase_option_details',
            'quantity_requested',
            'unit_price',
            'line_total',
            'product_name',
            'product_sku',
            'brand',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'line_total']

    def validate(self, data):
        """Validaciones adicionales."""
        # Validar que la opción de compra sea del mismo proveedor que la orden
        if 'order' in self.context and 'purchase_option' in data:
            order = self.context['order']
            if data['purchase_option'].supplier != order.supplier:
                raise serializers.ValidationError({
                    'purchase_option': 'La opción de compra debe ser del mismo proveedor que la orden.'
                })
        return data


class PurchaseOrderItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializer específico para crear items de orden de compra.
    """
    
    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id',
            'order',
            'purchase_option',
            'quantity_requested',
            'unit_price',
            'line_total',
            'created_at'
        ]
        read_only_fields = ['id', 'line_total', 'created_at']

    def validate_purchase_option(self, value):
        """Validar que la opción de compra esté vigente."""
        if not value.is_currently_valid():
            raise serializers.ValidationError(
                "La opción de compra seleccionada no está vigente."
            )
        return value


class PurchaseOrderItemForOrderCreateSerializer(serializers.ModelSerializer):
    """
    Serializer específico para items anidados en creación de órdenes.
    No incluye el campo 'order' porque se asigna automáticamente.
    """
    
    class Meta:
        model = PurchaseOrderItem
        fields = [
            'purchase_option',
            'quantity_requested',
            'unit_price'
        ]

    def validate_purchase_option(self, value):
        """Validar que la opción de compra esté vigente."""
        if not value.is_currently_valid():
            raise serializers.ValidationError(
                "La opción de compra seleccionada no está vigente."
            )
        return value


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """
    Serializer básico para órdenes de compra.
    """
    supplier_details = SupplierSerializer(source='supplier', read_only=True)
    destination_details = LocationSerializer(source='destination', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status = serializers.CharField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    can_be_modified = serializers.BooleanField(read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id',
            'supplier',
            'supplier_details',
            'destination',
            'destination_details',
            'order_date',
            'status',
            'status_display',
            'payment_status',
            'created_by',
            'created_by_username',
            'notes',
            'total_amount',
            'total_items',
            'can_be_modified',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_amount', 'total_items']

    def validate_supplier(self, value):
        """Validar que el proveedor tenga opciones de compra vigentes."""
        if not value.purchase_options.filter(
            valid_from__lte=timezone.localdate()
        ).exists():
            raise serializers.ValidationError(
                "El proveedor seleccionado no tiene opciones de compra vigentes."
            )
        return value


class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detallado para órdenes de compra incluyendo items.
    """
    supplier_details = SupplierSerializer(source='supplier', read_only=True)
    destination_details = LocationSerializer(source='destination', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status = serializers.CharField(read_only=True)
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    can_be_modified = serializers.BooleanField(read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id',
            'supplier',
            'supplier_details',
            'destination',
            'destination_details',
            'order_date',
            'status',
            'status_display',
            'payment_status',
            'created_by',
            'created_by_username',
            'notes',
            'items',
            'total_amount',
            'total_items',
            'can_be_modified',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_amount', 'total_items']


class PurchaseOrderCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear órdenes de compra con items.
    """
    items = PurchaseOrderItemForOrderCreateSerializer(many=True, write_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier',
            'destination',
            'order_date',
            'notes',
            'items'
        ]

    def validate_items(self, value):
        """Validar que se incluyan items en la orden."""
        if not value:
            raise serializers.ValidationError("Debe incluir al menos un item en la orden.")
        return value

    def validate(self, data):
        """Validaciones adicionales."""
        # Validar que todas las opciones de compra sean del mismo proveedor
        supplier = data.get('supplier')
        items = data.get('items', [])
        
        for item in items:
            if item['purchase_option'].supplier != supplier:
                raise serializers.ValidationError({
                    'items': f"Todos los items deben ser del proveedor {supplier.name}."
                })
        
        return data

    def create(self, validated_data):
        """Crear orden con items."""
        items_data = validated_data.pop('items')
        
        # Establecer el usuario creador
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user

        # Crear la orden
        purchase_order = PurchaseOrder.objects.create(**validated_data)

        # Crear los items
        for item_data in items_data:
            PurchaseOrderItem.objects.create(
                order=purchase_order,
                **item_data
            )

        return purchase_order


class AlternativeBrandSerializer(serializers.Serializer):
    """
    Serializer para mostrar marcas alternativas de un producto.
    """
    purchase_option_id = serializers.IntegerField()
    supplier_name = serializers.CharField()
    brand = serializers.CharField()
    purchase_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    valid_from = serializers.DateField()
    valid_to = serializers.DateField(allow_null=True)
    is_currently_valid = serializers.BooleanField()


class ProductAlternativesSerializer(serializers.Serializer):
    """
    Serializer para mostrar productos con marcas alternativas disponibles.
    """
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    alternatives = AlternativeBrandSerializer(many=True) 


class PurchaseOrderPaymentSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    cash_name = serializers.CharField(source='cash.location.name', read_only=True, default=None)
    is_annulled = serializers.BooleanField(read_only=True)
    annulled_at = serializers.DateTimeField(read_only=True)
    annulled_by_username = serializers.CharField(source='annulled_by.username', read_only=True, default=None)
    order_id = serializers.IntegerField(source='order.id', read_only=True)

    class Meta:
        model = PurchaseOrderPayment
        fields = [
            'id', 'order', 'order_id', 'amount', 'date', 'user', 'user_username',
            'notes', 'cash', 'cash_name', 'is_annulled', 'annulled_at', 'annulled_by', 'annulled_by_username'
        ]
        read_only_fields = ['id', 'date', 'is_annulled', 'annulled_at', 'annulled_by', 'annulled_by_username', 'user_username', 'cash_name', 'order_id']

    def validate(self, data):
        order = data.get('order') or self.instance.order if self.instance else None
        amount = data.get('amount')
        if order and amount and not data.get('is_annulled', False):
            total_paid = order.get_total_paid(exclude_payment=self.instance) if self.instance else order.get_total_paid()
            if total_paid + amount > order.get_total_amount():
                raise serializers.ValidationError({'amount': 'No se puede pagar más del total de la orden.'})
        return data 
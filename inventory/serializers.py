from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Location, InventoryStock, InventoryMovement
from catalogs.models import Product
from django.contrib.auth.models import User


class LocationSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Location."""
    
    total_products = serializers.SerializerMethodField()
    
    class Meta:
        model = Location
        fields = [
            'id', 'name', 'type', 'address', 'created_at', 'total_products'
        ]
        read_only_fields = ['id', 'created_at', 'total_products']
    
    def get_total_products(self, obj):
        """Devuelve el total de productos diferentes en esta ubicación."""
        return obj.product_stocks.filter(quantity__gt=0).count()

    def validate_type(self, value):
        """Validar tipo de ubicación."""
        if value not in ['sede', 'bodega']:
            raise serializers.ValidationError("Tipo de ubicación inválido.")
        return value


class InventoryStockSerializer(serializers.ModelSerializer):
    """Serializer para el modelo InventoryStock."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_unit = serializers.CharField(source='product.unit', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    location_type = serializers.CharField(source='location.get_type_display', read_only=True)
    
    class Meta:
        model = InventoryStock
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'product_unit',
            'location', 'location_name', 'location_type', 'quantity', 'last_updated'
        ]
        read_only_fields = ['id', 'last_updated']

    def validate_quantity(self, value):
        """Validar que la cantidad no sea negativa."""
        if value < 0:
            raise serializers.ValidationError("La cantidad no puede ser negativa.")
        return value


class InventoryMovementSerializer(serializers.ModelSerializer):
    """Serializer para el modelo InventoryMovement."""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    location_type = serializers.CharField(source='location.get_type_display', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    
    class Meta:
        model = InventoryMovement
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'location', 'location_name', 'location_type',
            'movement_type', 'movement_type_display', 'quantity',
            'occurred_at', 'expiry_date', 'user', 'user_username', 'notes'
        ]
        read_only_fields = ['id', 'occurred_at']

    def validate_quantity(self, value):
        """Validar que la cantidad sea positiva."""
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a cero.")
        return value

    def validate_movement_type(self, value):
        """Validar tipo de movimiento."""
        if value not in ['in', 'out']:
            raise serializers.ValidationError("Tipo de movimiento inválido.")
        return value
    
    def create(self, validated_data):
        """Al crear un movimiento, asignar el usuario actual si no se especifica."""
        if 'user' not in validated_data or validated_data['user'] is None:
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                validated_data['user'] = request.user
        
        try:
            return super().create(validated_data)
        except DjangoValidationError as e:
            # Convertir ValidationError de Django a DRF ValidationError
            if hasattr(e, 'message_dict'):
                raise serializers.ValidationError(e.message_dict)
            else:
                raise serializers.ValidationError(str(e))

    def update(self, instance, validated_data):
        """Actualizar movimiento con validaciones."""
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as e:
            # Convertir ValidationError de Django a DRF ValidationError
            if hasattr(e, 'message_dict'):
                raise serializers.ValidationError(e.message_dict)
            else:
                raise serializers.ValidationError(str(e))


class StockAlertSerializer(serializers.Serializer):
    """Serializer para alertas de stock bajo."""
    
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    location_id = serializers.IntegerField()
    location_name = serializers.CharField()
    current_quantity = serializers.IntegerField()
    alert_type = serializers.CharField()  # 'low_stock', 'out_of_stock'


class ExpiryAlertSerializer(serializers.Serializer):
    """Serializer para alertas de productos próximos a vencer."""
    
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    location_id = serializers.IntegerField()
    location_name = serializers.CharField()
    expiry_date = serializers.DateField()
    days_to_expiry = serializers.IntegerField()
    quantity = serializers.IntegerField()


class StockSummarySerializer(serializers.Serializer):
    """Serializer para resumen de stock por producto."""
    
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    product_unit = serializers.CharField()
    total_quantity = serializers.IntegerField()
    locations = serializers.ListField(
        child=serializers.DictField(), 
        help_text="Lista de ubicaciones con sus cantidades"
    ) 
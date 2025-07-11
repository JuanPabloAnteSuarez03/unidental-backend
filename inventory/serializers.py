from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Location, InventoryStock, InventoryMovement
from catalogs.models import Product, ProductBatch
from catalogs.serializers import ProductSummarySerializer, ProductBatchSerializer
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
    """
    Serializer para el modelo InventoryStock.
    Actualizado para manejar lotes.
    """
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_unit = serializers.CharField(source='product.unit', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    location_type = serializers.CharField(source='location.type', read_only=True)
    
    # Campos para lotes
    batch_details = ProductBatchSerializer(source='batch', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    expiry_date = serializers.DateField(source='batch.expiry_date', read_only=True)
    days_to_expiry = serializers.ReadOnlyField(source='batch.days_to_expiry')
    is_expired = serializers.ReadOnlyField(source='batch.is_expired')
    
    class Meta:
        model = InventoryStock
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'product_unit',
            'location', 'location_name', 'location_type', 
            'batch', 'batch_details', 'batch_number', 'expiry_date', 
            'days_to_expiry', 'is_expired',
            'quantity', 'last_updated'
        ]
        read_only_fields = ['id', 'last_updated']

    def validate_quantity(self, value):
        """Validar que la cantidad no sea negativa."""
        if value < 0:
            raise serializers.ValidationError("La cantidad no puede ser negativa.")
        return value

    def validate(self, data):
        """Validaciones del stock de inventario."""
        product = data.get('product')
        batch = data.get('batch')
        
        # Validar que si el producto requiere control de lotes, se especifique un lote
        if product and product.requires_batch_control and not batch:
            raise serializers.ValidationError({
                'batch': 'Este producto requiere especificar un lote.'
            })
        
        # Validar que si el producto no requiere control de lotes, no se especifique un lote
        if product and not product.requires_batch_control and batch:
            raise serializers.ValidationError({
                'batch': 'Este producto no requiere control de lotes.'
            })
        
        # Validar que el batch corresponde al producto
        if batch and product and batch.product != product:
            raise serializers.ValidationError({
                'batch': 'El lote no corresponde al producto seleccionado.'
            })
        
        return data


class InventoryMovementSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo InventoryMovement.
    Actualizado para manejar lotes y productos compuestos.
    """
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    location_type = serializers.CharField(source='location.type', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Campos para lotes
    batch_details = ProductBatchSerializer(source='batch', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    
    # Campos para productos compuestos
    related_movement_id = serializers.IntegerField(source='related_composite_movement.id', read_only=True)

    # Campos para transferencias
    destination_location_name = serializers.CharField(source='destination_location.name', read_only=True)
    related_transfer_movement_id = serializers.IntegerField(source='related_transfer_movement.id', read_only=True)

    class Meta:
        model = InventoryMovement
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'location', 'location_name', 'location_type',
            'destination_location', 'destination_location_name',
            'batch', 'batch_details', 'batch_number',
            'movement_type', 'movement_type_display', 'quantity', 'status', 'status_display',
            'is_internal_transfer', 'occurred_at', 'user', 'user_username', 'notes',
            'related_composite_movement', 'related_movement_id',
            'related_transfer_movement', 'related_transfer_movement_id'
        ]
        read_only_fields = ['id', 'occurred_at', 'related_transfer_movement']

    def validate_quantity(self, value):
        """Validar que la cantidad sea positiva."""
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a cero.")
        return value

    def validate_movement_type(self, value):
        """Validar tipo de movimiento."""
        if value not in ['in', 'out', 'composite_conversion']:
            raise serializers.ValidationError("Tipo de movimiento inválido.")
        return value

    def validate(self, data):
        """Validaciones del movimiento de inventario."""
        product = data.get('product')
        batch = data.get('batch')
        movement_type = data.get('movement_type')
        
        # Validar que si el producto requiere control de lotes, se especifique un lote
        if product and product.requires_batch_control and not batch:
            raise serializers.ValidationError({
                'batch': 'Este producto requiere especificar un lote.'
            })
        
        # Validar que si el producto no requiere control de lotes, no se especifique un lote
        if product and not product.requires_batch_control and batch:
            raise serializers.ValidationError({
                'batch': 'Este producto no requiere control de lotes.'
            })
        
        # Validar que el batch corresponde al producto
        if batch and product and batch.product != product:
            raise serializers.ValidationError({
                'batch': 'El lote no corresponde al producto seleccionado.'
            })
        
        # Validar destino en transferencias
        is_internal_transfer = data.get('is_internal_transfer')
        destination_location = data.get('destination_location')
        movement_type = data.get('movement_type')

        if is_internal_transfer and movement_type == 'out' and not destination_location:
            raise serializers.ValidationError({
                'destination_location': 'Se requiere una ubicación de destino para las transferencias de salida.'
            })

        return data
    
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
    
    # Campos para lotes
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    batch_number = serializers.CharField(required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)


class ExpiryAlertSerializer(serializers.Serializer):
    """Serializer para alertas de productos próximos a vencer."""
    
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    location_id = serializers.IntegerField()
    location_name = serializers.CharField()
    batch_id = serializers.IntegerField()
    batch_number = serializers.CharField()
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
    requires_batch_control = serializers.BooleanField()
    locations = serializers.ListField(
        child=serializers.DictField(), 
        help_text="Lista de ubicaciones con sus cantidades y lotes"
    )


class CompositeBreakdownSerializer(serializers.Serializer):
    """Serializer para desarmar productos compuestos."""
    
    composite_product = serializers.IntegerField(help_text="ID del producto compuesto a desarmar")
    location = serializers.IntegerField(help_text="ID de la ubicación donde realizar el desarmado")
    quantity = serializers.IntegerField(min_value=1, help_text="Cantidad de unidades compuestas a desarmar")
    notes = serializers.CharField(required=False, allow_blank=True, help_text="Notas adicionales")

    def validate_composite_product(self, value):
        """Validar que el producto existe y es compuesto."""
        try:
            product = Product.objects.get(id=value)
            if not product.is_composite():
                raise serializers.ValidationError("El producto debe ser de tipo compuesto/kit.")
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("El producto no existe.")


class BatchStockSerializer(serializers.Serializer):
    """Serializer para mostrar stock agrupado por lotes de un producto específico."""
    
    batch_id = serializers.IntegerField()
    batch_number = serializers.CharField()
    manufacturing_date = serializers.DateField(allow_null=True)
    expiry_date = serializers.DateField()
    days_to_expiry = serializers.IntegerField()
    is_expired = serializers.BooleanField()
    supplier_reference = serializers.CharField(allow_null=True)
    notes = serializers.CharField(allow_null=True)
    
    # Stock por ubicación para este lote
    locations = serializers.ListField(
        child=serializers.DictField(),
        help_text="Lista de ubicaciones con stock de este lote"
    )
    total_quantity = serializers.IntegerField(help_text="Cantidad total del lote en todas las ubicaciones")


class BatchLocationStockSerializer(serializers.Serializer):
    """Serializer para mostrar stock de un lote específico por ubicación."""
    
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    product_unit = serializers.CharField()
    requires_batch_control = serializers.BooleanField()
    
    batch_id = serializers.IntegerField()
    batch_number = serializers.CharField()
    expiry_date = serializers.DateField()
    days_to_expiry = serializers.IntegerField()
    is_expired = serializers.BooleanField()
    
    # Stock por ubicación
    locations = serializers.ListField(
        child=serializers.DictField(),
        help_text="Lista de ubicaciones con stock de este lote específico"
    )
    total_quantity = serializers.IntegerField(help_text="Cantidad total del lote en todas las ubicaciones")


class ProductBatchesStockSerializer(serializers.Serializer):
    """Serializer para mostrar todos los lotes de un producto con su stock por ubicación."""
    
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    product_unit = serializers.CharField()
    requires_batch_control = serializers.BooleanField()
    
    # Lista de lotes con su stock
    batches = BatchStockSerializer(many=True, help_text="Lista de lotes del producto con stock por ubicación")
    total_stock = serializers.IntegerField(help_text="Stock total del producto (suma de todos los lotes)")


class LocationBatchStockSerializer(serializers.Serializer):
    """Serializer para mostrar el stock de lotes en una ubicación específica."""
    
    location_id = serializers.IntegerField()
    location_name = serializers.CharField()
    location_type = serializers.CharField()
    
    # Productos con lotes en esta ubicación
    products = serializers.ListField(
        child=serializers.DictField(),
        help_text="Lista de productos con lotes en esta ubicación"
    ) 
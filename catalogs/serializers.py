from rest_framework import serializers
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Category, Product, ProductComponent, ProductBatch, ProductConversion, SkuCategory, SkuSubCategory, SkuType


# --- Serializadores para la estructura del SKU ---

class SkuCategorySerializer(serializers.ModelSerializer):
    """Serializer para Categorías de SKU."""
    class Meta:
        model = SkuCategory
        fields = ['id', 'code', 'name']

class SkuSubCategorySerializer(serializers.ModelSerializer):
    """Serializer para Subcategorías de SKU."""
    class Meta:
        model = SkuSubCategory
        fields = ['id', 'category', 'code', 'name']

class SkuTypeSerializer(serializers.ModelSerializer):
    """Serializer para Tipos de SKU."""
    class Meta:
        model = SkuType
        fields = ['id', 'subcategory', 'code', 'name']


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo Category.
    Incluye todos los campos del modelo.
    """
    class Meta:
        model = Category
        fields = '__all__' # Incluye id, name, description, created_at, updated_at
        read_only_fields = ('created_at', 'updated_at')


class ProductBatchSerializer(serializers.ModelSerializer):
    """Serializador para el modelo ProductBatch."""
    
    is_expired = serializers.ReadOnlyField()
    days_to_expiry = serializers.ReadOnlyField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = ProductBatch
        fields = [
            'id', 'product', 'product_name', 'batch_number', 
            'manufacturing_date', 'expiry_date', 'supplier_reference', 
            'notes', 'is_expired', 'days_to_expiry', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')

    def validate(self, data):
        """Validaciones del lote."""
        if data.get('manufacturing_date') and data.get('expiry_date'):
            if data['manufacturing_date'] >= data['expiry_date']:
                raise serializers.ValidationError({
                    'manufacturing_date': 'La fecha de fabricación debe ser anterior a la fecha de vencimiento.'
                })
        
        # Validar que la fecha de vencimiento no sea en el pasado
        if data.get('expiry_date') and data['expiry_date'] < timezone.now().date():
            raise serializers.ValidationError({
                'expiry_date': 'La fecha de vencimiento no puede ser en el pasado.'
            })
        
        return data


class ProductComponentSerializer(serializers.ModelSerializer):
    """Serializador para el modelo ProductComponent."""
    
    composite_product_name = serializers.CharField(source='composite_product.name', read_only=True)
    component_product_name = serializers.CharField(source='component_product.name', read_only=True)
    component_product_sku = serializers.CharField(source='component_product.sku', read_only=True)
    
    class Meta:
        model = ProductComponent
        fields = [
            'id', 'composite_product', 'composite_product_name',
            'component_product', 'component_product_name', 'component_product_sku',
            'quantity', 'created_at'
        ]
        read_only_fields = ('created_at',)

    def validate(self, data):
        """Validaciones del componente."""
        if data['composite_product'] == data['component_product']:
            raise serializers.ValidationError("Un producto no puede ser componente de sí mismo.")
        
        if data['composite_product'].product_type != 'composite':
            raise serializers.ValidationError({
                'composite_product': 'El producto padre debe ser de tipo Compuesto/Kit.'
            })
        
        if data['component_product'].product_type == 'composite':
            raise serializers.ValidationError({
                'component_product': 'Un producto compuesto no puede ser componente de otro.'
            })
        
        return data


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo Product.
    Incluye información de componentes y lotes cuando sea relevante.
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    product_type_display = serializers.CharField(source='get_product_type_display', read_only=True)
    
    # Campos anidados para productos compuestos
    components = ProductComponentSerializer(source='composite_components', many=True, read_only=True)
    parent_kits = ProductComponentSerializer(source='component_of', many=True, read_only=True)
    
    # Campos para lotes (solo para productos que requieren control de lotes)
    batches = ProductBatchSerializer(many=True, read_only=True)
    active_batches_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'barcode', 'name', 'description', 'unit',
            'category', 'category_name', 'product_type', 'product_type_display',
            'requires_batch_control', 'min_stock_threshold', 'min_expiry_days_threshold',
            'sale_price',
            'components', 'parent_kits', 'batches', 'active_batches_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at', 'category_name', 'product_type_display')

    def get_active_batches_count(self, obj):
        """Retorna el número de lotes activos (no expirados)."""
        if not obj.requires_batch_control:
            return None
        
        return obj.batches.filter(expiry_date__gte=timezone.now().date()).count()

    def validate(self, data):
        """Validaciones del producto."""
        # Si se marca como compuesto, validar que no sea también componente
        if data.get('product_type') == 'composite':
            # Verificar que este producto no sea ya componente de otro
            if hasattr(self.instance, 'component_of') and self.instance.component_of.exists():
                raise serializers.ValidationError({
                    'product_type': 'Un producto que es componente de otro no puede ser compuesto.'
                })
        
        return data


class ProductSummarySerializer(serializers.ModelSerializer):
    """Serializador simplificado para listados y referencias."""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    product_type_display = serializers.CharField(source='get_product_type_display', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'barcode', 'name', 'description', 'unit', 'category', 'category_name', 
            'product_type', 'product_type_display', 'requires_batch_control',
            'min_stock_threshold', 'min_expiry_days_threshold', 'sale_price'
        ]


class ProductConversionSerializer(serializers.ModelSerializer):
    """Serializador para conversiones de productos."""
    
    from_product_name = serializers.CharField(source='from_product.name', read_only=True)
    from_product_sku = serializers.CharField(source='from_product.sku', read_only=True)
    to_product_name = serializers.CharField(source='to_product.name', read_only=True)
    to_product_sku = serializers.CharField(source='to_product.sku', read_only=True)
    
    class Meta:
        model = ProductConversion
        fields = [
            'id', 'from_product', 'from_product_name', 'from_product_sku',
            'to_product', 'to_product_name', 'to_product_sku',
            'conversion_rate', 'is_reversible', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')


class ConversionExecutionSerializer(serializers.Serializer):
    """Serializer para ejecutar conversiones manuales."""
    
    conversion_id = serializers.IntegerField()
    quantity_to_convert = serializers.IntegerField(min_value=1)
    location_id = serializers.IntegerField()
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_conversion_id(self, value):
        """Validar que la conversión existe."""
        try:
            ProductConversion.objects.get(id=value)
        except ProductConversion.DoesNotExist:
            raise serializers.ValidationError("La conversión especificada no existe.")
        return value
    
    def validate_location_id(self, value):
        """Validar que la ubicación existe."""
        from inventory.models import Location
        try:
            Location.objects.get(id=value)
        except Location.DoesNotExist:
            raise serializers.ValidationError("La ubicación especificada no existe.")
        return value
    
    def validate_batch_id(self, value):
        """Validar que el lote existe si se especifica."""
        if value is not None:
            try:
                ProductBatch.objects.get(id=value)
            except ProductBatch.DoesNotExist:
                raise serializers.ValidationError("El lote especificado no existe.")
        return value
    
    def validate(self, data):
        """Validaciones a nivel de objeto."""
        conversion = ProductConversion.objects.get(id=data['conversion_id'])
        from inventory.models import Location
        location = Location.objects.get(id=data['location_id'])
        batch = None
        
        # Validar que se especifica lote si el producto lo requiere
        if conversion.from_product.requires_batch_control and not data.get('batch_id'):
            raise serializers.ValidationError({
                'batch': ['Este producto requiere especificar un lote.']
            })
        
        if data.get('batch_id'):
            batch = ProductBatch.objects.get(id=data['batch_id'])
            
            # Validar que el lote pertenece al producto origen
            if batch.product != conversion.from_product:
                raise serializers.ValidationError({
                    'batch_id': 'El lote especificado no pertenece al producto origen de la conversión.'
                })
        
        # Validar que hay suficiente stock
        from inventory.models import InventoryStock
        if batch:
            stock_record = InventoryStock.objects.filter(
                product=conversion.from_product,
                location=location,
                batch=batch
            ).first()
            available = stock_record.quantity if stock_record else 0
        else:
            available = InventoryStock.get_total_stock(conversion.from_product, location)
        
        if available < data['quantity_to_convert']:
            raise serializers.ValidationError({
                'quantity_to_convert': f'Stock insuficiente. Disponible: {available}, Requerido: {data["quantity_to_convert"]}'
            })
        
        return data


class ConversionSuggestionSerializer(serializers.Serializer):
    """Serializer para sugerencias de conversión cuando no hay stock suficiente."""
    
    product_id = serializers.IntegerField()
    location_id = serializers.IntegerField()
    required_quantity = serializers.IntegerField(min_value=1)
    
    def validate_product_id(self, value):
        """Validar que el producto existe."""
        try:
            Product.objects.get(id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("El producto especificado no existe.")
        return value
    
    def validate_location_id(self, value):
        """Validar que la ubicación existe."""
        from inventory.models import Location
        try:
            Location.objects.get(id=value)
        except Location.DoesNotExist:
            raise serializers.ValidationError("La ubicación especificada no existe.")
        return value 
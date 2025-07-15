from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from .models import Customer, Sale, SaleItem, Return, ReturnItem
from catalogs.models import Product, ProductBatch, ProductComponent, ProductConversion
from catalogs.serializers import ProductSerializer, ProductSummarySerializer, ProductBatchSerializer
from inventory.models import InventoryStock, InventoryMovement, Location
from inventory.serializers import LocationSerializer
from django.db import models
from django.db import transaction
from decimal import Decimal


class InsufficientStockError(APIException):
    """Excepción para cuando no hay stock suficiente con sugerencias de conversión."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Stock insuficiente'
    default_code = 'insufficient_stock'


class CustomerSerializer(serializers.ModelSerializer):
    """Serializador para el modelo de Cliente."""
    
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'email', 'address', 'birthday', 'emergency_contact', 'notes', 'created_at']
        read_only_fields = ['created_at']


class SaleItemSerializer(serializers.ModelSerializer):
    """Serializador para los items de venta con soporte para lotes."""
    
    product_details = ProductSerializer(source='product', read_only=True)
    batch_details = ProductBatchSerializer(source='batch', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_details', 'batch', 'batch_details', 'quantity', 'unit_price', 'subtotal']

    def get_subtotal(self, obj):
        """Calcula el subtotal del item multiplicando cantidad por precio unitario."""
        return obj.quantity * obj.unit_price

    def validate(self, data):
        """Validaciones del item de venta con lotes."""
        quantity = data.get('quantity')
        product = data.get('product')
        batch = data.get('batch')
        
        if quantity and quantity <= 0:
            raise serializers.ValidationError({
                'quantity': 'La cantidad debe ser mayor a cero'
            })
        
        # Validar que si el producto no requiere control de lotes, no se especifique un lote
        if product and not product.requires_batch_control and batch:
            raise serializers.ValidationError({
                'batch': 'Este producto no requiere control de lotes.'
            })
        
        # Validar que si el producto requiere control de lotes, se especifique un lote
        if product and product.requires_batch_control and not batch:
            raise serializers.ValidationError({
                'batch': 'Este producto requiere especificar un lote.'
            })
        
        # Validar que el batch corresponde al producto (solo si se especifica un lote)
        if batch and product and batch.product != product:
            raise serializers.ValidationError({
                'batch': 'El lote no corresponde al producto seleccionado.'
            })
        
        return data


class SaleSerializer(serializers.ModelSerializer):
    """Serializador para las ventas con soporte para items anidados y productos independientes."""
    
    items = SaleItemSerializer(many=True)
    customer_details = CustomerSerializer(source='customer', read_only=True)
    location_details = LocationSerializer(source='location', read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'customer', 'customer_details', 'location', 'location_details',
            'sale_date', 'sale_type', 'should_invoice', 'total_gross', 'total_net', 'items'
        ]
        read_only_fields = ['sale_date', 'total_gross', 'total_net']

    @transaction.atomic
    def create(self, validated_data):
        """
        Crea una venta con sus items asociados.
        Actualiza automáticamente el stock de los productos usando la sede especificada.
        Todos los productos se manejan como productos independientes.
        """
        items_data = validated_data.pop('items')
        sale = Sale.objects.create(**validated_data)
        sale_location = sale.location

        for item_data in items_data:
            product = item_data['product']
            batch = item_data.get('batch')
            quantity = item_data['quantity']
            
            # Todos los productos se procesan como productos simples independientes
            self._process_simple_sale(product, batch, quantity, sale, sale_location)
            
            # Crear el item de venta
            SaleItem.objects.create(sale=sale, **item_data)

        return sale

    def _check_and_reserve_stock(self, product, batch, quantity, location):
        """Verifica stock para un producto específico y sugiere conversiones si no hay suficiente."""
        if product.requires_batch_control:
            if not batch:
                raise serializers.ValidationError({
                    'items': f'El producto {product.name} requiere especificar un lote.'
                })
            
            try:
                stock_location = InventoryStock.objects.get(
                    product=product, 
                    location=location,
                    batch=batch
                )
                
                if stock_location.quantity < quantity:
                    # Buscar sugerencias de conversión para este producto y lote específico
                    suggestions = self._get_conversion_suggestions(product, location, quantity)
                    
                    raise InsufficientStockError({
                        'product': product.name,
                        'batch': batch.batch_number,
                        'available': stock_location.quantity,
                        'required': quantity,
                        'deficit': quantity - stock_location.quantity,
                        'suggestions': suggestions,
                        'message': f'Stock insuficiente del lote {batch.batch_number} del producto {product.name} en {location.name}.'
                    })
                
            except InventoryStock.DoesNotExist:
                suggestions = self._get_conversion_suggestions(product, location, quantity)
                
                raise InsufficientStockError({
                    'product': product.name,
                    'batch': batch.batch_number,
                    'available': 0,
                    'required': quantity,
                    'deficit': quantity,
                    'suggestions': suggestions,
                    'message': f'No hay stock del lote {batch.batch_number} del producto {product.name} en {location.name}'
                })
        else:
            # Producto sin control de lotes
            total_stock = InventoryStock.get_total_stock(product, location)
            
            if total_stock < quantity:
                suggestions = self._get_conversion_suggestions(product, location, quantity)
                
                raise InsufficientStockError({
                    'product': product.name,
                    'available': total_stock,
                    'required': quantity,
                    'deficit': quantity - total_stock,
                    'suggestions': suggestions,
                    'message': f'Stock insuficiente del producto {product.name} en {location.name}.'
                })

    def _get_conversion_suggestions(self, product, location, required_quantity):
        """Obtiene sugerencias de conversión para un producto cuando no hay stock suficiente."""
        current_stock = InventoryStock.get_total_stock(product, location)
        deficit = max(0, required_quantity - current_stock)
        
        if deficit == 0:
            return []
        
        # Buscar conversiones que puedan generar este producto
        reverse_conversions = ProductConversion.get_reverse_conversions(product, location)
        
        suggestions = []
        for conversion in reverse_conversions:
            available_stock = InventoryStock.get_total_stock(conversion.from_product, location)
            if available_stock > 0:
                can_provide = available_stock * conversion.conversion_rate
                units_needed = max(1, (deficit + conversion.conversion_rate - 1) // conversion.conversion_rate)
                
                suggestions.append({
                    'conversion_id': conversion.id,
                    'from_product': {
                        'id': conversion.from_product.id,
                        'name': conversion.from_product.name,
                        'sku': conversion.from_product.sku
                    },
                    'to_product': {
                        'id': conversion.to_product.id,
                        'name': conversion.to_product.name,
                        'sku': conversion.to_product.sku
                    },
                    'conversion_rate': conversion.conversion_rate,
                    'available_stock': available_stock,
                    'can_provide': can_provide,
                    'units_needed': units_needed,
                    'would_convert_to': min(units_needed * conversion.conversion_rate, deficit)
                })
        
        # Ordenar por cantidad que pueden proveer (descendente)
        suggestions.sort(key=lambda x: x['can_provide'], reverse=True)
        
        return suggestions

    def _process_simple_sale(self, product, batch, quantity, sale, location):
        """Procesa la venta de cualquier producto como producto simple independiente."""
        self._check_and_reserve_stock(product, batch, quantity, location)
        self._create_sale_movement(product, batch, quantity, sale, location, 'Venta de producto')

    def _create_sale_movement(self, product, batch, quantity, sale, location, notes):
        """Crea un movimiento de inventario de salida para la venta."""
        InventoryMovement.objects.create(
            product=product,
            location=location,
            batch=batch,
            movement_type='out',
            quantity=quantity,
            notes=f'{notes} - Venta #{sale.id}',
            user=getattr(self.context.get('request'), 'user', None)
        )

    def validate(self, data):
        """Validaciones a nivel de venta."""
        location = data.get('location')
        items = data.get('items', [])
        
        if not items:
            raise serializers.ValidationError({
                'items': 'La venta debe tener al menos un item'
            })
        
        validation_errors = {}
        
        # Validar cada item individualmente
        for idx, item_data in enumerate(items):
            product = item_data.get('product')
            batch = item_data.get('batch')
            quantity = item_data.get('quantity')
            
            if not product or not quantity:
                continue
                
            try:
                # Validar stock de cada producto independientemente
                self._validate_simple_stock(product, batch, quantity, location)
            except InsufficientStockError as e:
                validation_errors[f'items[{idx}]'] = e.detail
            except serializers.ValidationError as e:
                validation_errors[f'items[{idx}]'] = e.detail
        
        if validation_errors:
            raise serializers.ValidationError(validation_errors)
        
        return data
    
    def _validate_simple_stock(self, product, batch, quantity, location):
        """Valida que hay suficiente stock del producto."""
        try:
            self._check_and_reserve_stock(product, batch, quantity, location)
        except InsufficientStockError:
            raise
        except serializers.ValidationError:
            raise


class ReturnItemSerializer(serializers.ModelSerializer):
    """Serializador para los items de devolución."""
    
    product_details = ProductSerializer(source='product', read_only=True)
    sale_item_details = SaleItemSerializer(source='sale_item', read_only=True)
    
    class Meta:
        model = ReturnItem
        fields = [
            'id', 'return_obj', 'sale_item', 'sale_item_details', 
            'product', 'product_details', 'quantity_returned', 
            'unit_price', 'subtotal'
        ]
        read_only_fields = ['subtotal']
        extra_kwargs = {'return_obj': {'required': False}}
    
    def update(self, instance, validated_data):
        """
        Actualiza un item de devolución y ajusta el inventario.
        """
        original_quantity = instance.quantity_returned
        
        # Actualiza la instancia con la nueva cantidad
        instance.quantity_returned = validated_data.get('quantity_returned', original_quantity)
        instance.save()

        # Ajustar inventario para la diferencia
        quantity_diff = instance.quantity_returned - original_quantity
        if quantity_diff != 0:
            InventoryMovement.objects.create(
                product=instance.product,
                location=instance.return_obj.location,
                movement_type='in' if quantity_diff > 0 else 'out',
                quantity=abs(quantity_diff),
                notes=f'Ajuste por actualización de item de devolución #{instance.id}'
            )

        return instance

    def validate(self, data):
        """Validaciones del item de devolución."""
        # Durante una actualización, algunos campos no estarán en `data`
        sale_item = data.get('sale_item') or getattr(self.instance, 'sale_item', None)
        product = data.get('product') or getattr(self.instance, 'product', None)
        quantity_returned = data.get('quantity_returned')

        if not sale_item or not product or quantity_returned is None:
            raise serializers.ValidationError("Faltan campos requeridos (sale_item, product, quantity_returned).")

        # Validar que el producto corresponde al item de venta
        if 'product' in data and product != sale_item.product:
            raise serializers.ValidationError({
                'product': 'El producto debe corresponder al item de venta original.'
            })
        
        # Validar cantidad disponible para devolver
        already_returned_qs = ReturnItem.objects.filter(sale_item=sale_item)
        if self.instance:
            already_returned_qs = already_returned_qs.exclude(pk=self.instance.pk)
            
        already_returned = already_returned_qs.aggregate(
            total=models.Sum('quantity_returned')
        )['total'] or 0
        
        available_to_return = sale_item.quantity - already_returned
        
        if quantity_returned > available_to_return:
            raise serializers.ValidationError({
                'quantity_returned': f'No se puede devolver más cantidad de la disponible. '
                                   f'Disponible para devolver: {available_to_return}'
            })
        
        return data


class ReturnSerializer(serializers.ModelSerializer):
    """Serializador para las devoluciones con soporte para items anidados."""
    
    items = ReturnItemSerializer(many=True, required=False)
    customer_details = CustomerSerializer(source='customer', read_only=True)
    location_details = LocationSerializer(source='location', read_only=True)
    original_sale_details = SaleSerializer(source='original_sale', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = Return
        fields = [
            'id', 'original_sale', 'original_sale_details', 'customer', 
            'customer_details', 'location', 'location_details', 'return_date', 
            'reason', 'reason_display', 'notes', 'total_amount', 'items'
        ]
        read_only_fields = ['return_date', 'total_amount']
    
    def create(self, validated_data):
        """
        Crea una devolución con sus items asociados.
        La lógica de inventario se maneja por señales en el modelo ReturnItem.
        """
        items_data = validated_data.pop('items', [])
        return_obj = Return.objects.create(**validated_data)
        
        for item_data in items_data:
            ReturnItem.objects.create(return_obj=return_obj, **item_data)
        
        return return_obj
    
    def update(self, instance, validated_data):
        """
        Actualiza una devolución. No se permite cambiar la venta original ni los items.
        """
        validated_data.pop('items', None) # No se gestionan items aquí
        validated_data.pop('original_sale', None) # No se puede cambiar la venta original
        return super().update(instance, validated_data)

    def validate(self, data):
        """Validaciones de la devolución."""
        
        # En creación, la venta original es obligatoria
        if not self.instance and 'original_sale' not in data:
            raise serializers.ValidationError({'original_sale': 'Este campo es requerido.'})

        # Validar que el cliente de la devolución corresponde al de la venta
        original_sale = data.get('original_sale') or getattr(self.instance, 'original_sale', None)
        if data.get('customer') and original_sale and data['customer'] != original_sale.customer:
            raise serializers.ValidationError({
                'customer': 'El cliente de la devolución no coincide con el de la venta original.'
            })
            
        return data

    def validate_items(self, items):
        """Valida que la devolución tenga al menos un item."""
        if not items:
            raise serializers.ValidationError("Se requiere al menos un item en la devolución.")
        return items


class ReturnItemSummarySerializer(serializers.ModelSerializer):
    """Serializador liviano para listados de items de devolución - OPTIMIZADO."""
    
    product_details = ProductSummarySerializer(source='product', read_only=True)
    return_id = serializers.IntegerField(source='return_obj.id', read_only=True)
    sale_id = serializers.IntegerField(source='sale_item.sale.id', read_only=True)
    
    class Meta:
        model = ReturnItem
        fields = [
            'id', 'return_id', 'sale_id', 'product_details', 
            'quantity_returned', 'unit_price', 'subtotal'
        ]
        read_only_fields = ['subtotal']


class ReturnSummarySerializer(serializers.ModelSerializer):
    """Serializador liviano para listados de devoluciones - OPTIMIZADO."""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    original_sale_id = serializers.IntegerField(source='original_sale.id', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = Return
        fields = [
            'id', 'original_sale_id', 'customer_name', 'location_name', 
            'return_date', 'reason', 'reason_display', 'total_amount'
        ]


# --- Excepciones personalizadas ---
# (Las excepciones específicas del sistema anterior se han removido) 